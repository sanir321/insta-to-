import os
import time
import json
import argparse
import pickle
import shutil
import random
from datetime import datetime
from dotenv import load_dotenv

# Google & YouTube API
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

# Downloading & Processing
import yt_dlp
import ffmpeg

# AI Gateway (OpenAI compatible)
from openai import OpenAI

# Load environment variables
load_dotenv()

# --- CONFIGURATION ---
DATA_DIR = "/app/data" if os.path.exists("/app/data") else "."
CLIENT_SECRETS_FILE = "client_secret.json" # Kept in root (part of build)
TOKEN_PICKLE_FILE = os.path.join(DATA_DIR, "youtube_token.pickle")
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

COMPLETED_URLS_FILE = os.path.join(DATA_DIR, "completed_reels.txt")
DOWNLOAD_DIR = os.path.join(DATA_DIR, "downloads")
COMPLETED_DIR = os.path.join(DATA_DIR, "completed")

# Kilo AI Config
KILO_API_KEY = os.getenv("KILO_API_KEY")
KILO_BASE_URL = "https://api.kilo.ai/api/gateway/"
KILO_MODEL = os.getenv("KILO_MODEL", "deepseek/deepseek-chat")

for folder in [DOWNLOAD_DIR, COMPLETED_DIR]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# --- AI CAPTION GENERATOR ---
def generate_ai_metadata(original_title, original_description):
    if not KILO_API_KEY:
        print("⚠️ No KILO_API_KEY found. Using default metadata.")
        return original_title, "Uploaded via InstaToYTAgent #Shorts #Reels"

    print("🤖 Generating AI metadata via Kilo AI...")
    client = OpenAI(api_key=KILO_API_KEY, base_url=KILO_BASE_URL)
    
    # Clean up input metadata
    context = f"Title: {original_title}\nCaption: {original_description}"
    
    prompt = f"""
    You are a viral YouTube Shorts expert. Create a catchy title and a high-engagement description based on the following Instagram Reel metadata:
    
    {context}
    
    Guidelines:
    1. The YouTube title should be short (<60 chars) and clicky.
    2. The description should summarize the video nicely.
    3. Include 3-5 relevant viral hashtags.
    4. Stay true to the original vibe of the content.
    
    Respond STRICTLY in JSON format: {{"title": "...", "description": "..."}}
    """
    
    try:
        response = client.chat.completions.create(
            model=KILO_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={ "type": "json_object" }
        )
        data = json.loads(response.choices[0].message.content)
        return data.get("title", original_title), data.get("description", "Uploaded via InstaToYTAgent #Shorts")
    except Exception as e:
        print(f"❌ Kilo AI failed: {e}")
        return original_title, "Uploaded via InstaToYTAgent #Shorts"

# --- VIDEO PROCESSOR (FFmpeg) ---
def process_video(input_path):
    print(f"🎬 Processing video to avoid copy detection...")
    output_path = input_path.replace(".mp4", "_processed.mp4")
    
    # We change the resolution slightly (e.g. 1080x1918 instead of 1080x1920)
    # and re-encode to change the hash.
    try:
        (
            ffmpeg
            .input(input_path)
            .filter('scale', 1080, 1918)
            .output(output_path, vcodec='libx264', crf=23, preset='fast', acodec='aac')
            .overwrite_output()
            .run(quiet=True)
        )
        return output_path
    except Exception as e:
        print(f"❌ FFmpeg processing failed: {e}")
        return input_path

# --- YOUTUBE AUTHENTICATION ---
def get_authenticated_service():
    credentials = None
    if os.path.exists(TOKEN_PICKLE_FILE):
        with open(TOKEN_PICKLE_FILE, 'rb') as token:
            credentials = pickle.load(token)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS_FILE, SCOPES)
            # Port 0 (dynamic) is best for Desktop Application credentials
            credentials = flow.run_local_server(port=0)
        
        with open(TOKEN_PICKLE_FILE, 'wb') as token:
            pickle.dump(credentials, token)

    return googleapiclient.discovery.build(
        YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, credentials=credentials)

# --- REEL DOWNLOADER ---
def download_reel(url):
    print(f"📥 Downloading Reel: {url}...")
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            video_filename = ydl.prepare_filename(info_dict)
            title = info_dict.get('title', 'Instagram Reel')
            description = info_dict.get('description', '')
            return video_filename, title, description
    except Exception as e:
        print(f"❌ Failed to download {url}: {e}")
        return None, None, None

# --- YOUTUBE UPLOADER ---
def upload_to_youtube(youtube, file_path, title, description, privacy='private'):
    print(f"📤 Uploading: {title} ({privacy})")
    
    body = {
        'snippet': {
            'title': title[:100],
            'description': description,
            'tags': ['Shorts', 'Reels', 'Viral'],
            'categoryId': '22'
        },
        'status': {
            'privacyStatus': privacy,
            'selfDeclaredMadeForKids': False
        }
    }

    insert_request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=MediaFileUpload(file_path, chunksize=-1, resumable=True)
    )

    response = None
    while response is None:
        status, response = insert_request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress() * 100)}%")

    print(f"✅ Uploaded! ID: {response['id']}")
    return response['id']

# --- STATE MANAGEMENT ---
def load_completed_urls():
    if os.path.exists(COMPLETED_URLS_FILE):
        with open(COMPLETED_URLS_FILE, 'r') as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_completed_url(url):
    with open(COMPLETED_URLS_FILE, 'a') as f:
        f.write(url + "\n")

# --- MAIN EXECUTION ---
def main():
    parser = argparse.ArgumentParser(description="Instagram Reel to YouTube Shorts Agent (PRO)")
    parser.add_argument("--file", default="reel_urls.txt", help="Path to Reel URLs")
    parser.add_argument("--daily", action="store_true", help="Post daily logic")
    parser.add_argument("--limit", type=int, default=1, help="Number of videos per run")
    parser.add_argument("--privacy", default="unlisted", choices=["public", "private", "unlisted"], help="Upload visibility (default: unlisted)")
    
    args = parser.parse_args()

    if not os.path.exists(CLIENT_SECRETS_FILE):
        print(f"❌ Error: {CLIENT_SECRETS_FILE} missing.")
        return

    youtube = get_authenticated_service()
    
    while True:
        completed_urls = load_completed_urls()
        
        if not os.path.exists(args.file):
            print(f"Waiting for {args.file}...")
            if not args.daily: break
            time.sleep(3600)
            continue

        with open(args.file, 'r') as f:
            all_urls = [line.strip() for line in f if line.strip()]

        new_urls = [u for u in all_urls if u not in completed_urls]
        
        if not new_urls:
            print("📭 No new URLs. Waiting...")
            if not args.daily: break
            time.sleep(3600)
            continue

        batch = new_urls[:(1 if args.daily else args.limit)]

        for url in batch:
            print(f"\n🚀 Processing: {url}")
            try:
                # 1. Download
                raw_path, raw_title, raw_desc = download_reel(url)
                if not raw_path: continue
                
                # 2. Process (FFmpeg)
                processed_path = process_video(raw_path)
                
                # 3. AI Metadata
                final_title, final_desc = generate_ai_metadata(raw_title, raw_desc)
                
                # 4. Upload
                upload_to_youtube(youtube, processed_path, final_title, final_desc, args.privacy)
                
                # 5. Save State & Cleanup
                save_completed_url(url)
                
                if os.path.exists(processed_path):
                    os.remove(processed_path)
                if os.path.exists(raw_path):
                    os.remove(raw_path)
                
                print(f"✅ Successfully finished {url} and cleaned up files.")

            except Exception as e:
                print(f"❌ Error: {e}")

        if not args.daily:
            break
        
        print("\n😴 Sleeping for 24 hours...")
        time.sleep(24 * 3600)

if __name__ == "__main__":
    main()
