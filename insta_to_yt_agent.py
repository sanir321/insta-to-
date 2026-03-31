import os
import time
import json
import argparse
import pickle
import shutil
import random
import base64
import threading
from datetime import datetime
from dotenv import load_dotenv

# Web Dashboard
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

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

# --- SECRETS DECODER ---
def setup_headless_secrets():
    if not os.path.exists(CLIENT_SECRETS_FILE) and os.getenv("GOOGLE_CLIENT_SECRET_B64"):
        print("🔓 Decoding Secret from env...")
        with open(CLIENT_SECRETS_FILE, "wb") as f:
            f.write(base64.b64decode(os.getenv("GOOGLE_CLIENT_SECRET_B64")))
    if not os.path.exists(TOKEN_PICKLE_FILE) and os.getenv("YOUTUBE_TOKEN_B64"):
        print("🔓 Decoding Token from env...")
        with open(TOKEN_PICKLE_FILE, "wb") as f:
            f.write(base64.b64decode(os.getenv("YOUTUBE_TOKEN_B64")))

# Prepare folders
for folder in [DOWNLOAD_DIR, COMPLETED_DIR]:
    os.makedirs(folder, exist_ok=True)

setup_headless_secrets()

# --- STATUS MANAGER (Dashboard Backend) ---
class StatusManager:
    def __init__(self):
        self.current_action = "Initializing..."
        self.total_uploads = 0
        self.last_upload_time = "Never"
        self.active_url = "None"
        self.progress = 0
        self.step_name = "Ready"
        self.is_running = False
        self.logs = []

    def update(self, action=None, progress=None, step=None, url=None):
        if action: self.current_action = action
        if progress is not None: self.progress = progress
        if step: self.step_name = step
        if url: self.active_url = url
        if action or step: self.log(f"{step or action}")

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_msg = f"[{timestamp}] {message}"
        print(formatted_msg)
        self.logs.append(formatted_msg)
        if len(self.logs) > 15: self.logs.pop(0)

    def mark_upload(self):
        self.total_uploads += 1
        self.last_upload_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

status = StatusManager()

# --- WEB DASHBOARD SETUP ---
app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/status")
async def get_status():
    return {
        "current_action": status.current_action,
        "total_uploads": status.total_uploads,
        "last_upload_time": status.last_upload_time,
        "active_url": status.active_url,
        "progress": status.progress,
        "step_name": status.step_name,
        "is_running": status.is_running,
        "logs": status.logs
    }

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

# --- MAIN AUTOMATION LOOP ---
def run_automation_loop(args):
    status.is_running = True
    status.log("🚀 Automation Loop Started")
    
    if not os.path.exists(CLIENT_SECRETS_FILE):
        status.log(f"❌ Error: {CLIENT_SECRETS_FILE} missing.")
        return

    try:
        status.update(action="Authenticating", progress=5, step="Google Auth")
        youtube = get_authenticated_service()
    except Exception as e:
        status.log(f"❌ Auth Failed: {e}")
        return

    while True:
        status.update(action="Checking URLs", progress=10, step="Scanning File")
        completed_urls = load_completed_urls()
        
        if not os.path.exists(args.file):
            status.update(action="Waiting for file", progress=0, step="Idle")
            if not args.daily: break
            time.sleep(60)
            continue

        with open(args.file, 'r') as f:
            all_urls = [line.strip() for line in f if line.strip()]

        new_urls = [u for u in all_urls if u not in completed_urls]
        
        if not new_urls:
            status.update(action="No new URLs", progress=0, step="Idle")
            if not args.daily: break
            status.update(action="Sleeping", step="Waiting for 1 hour")
            time.sleep(3600)
            continue

        batch = new_urls[:(1 if args.daily else args.limit)]

        for url in batch:
            status.update(action="Processing", progress=20, step="Starting", url=url)
            try:
                # 1. Download
                status.update(progress=30, step="Downloading from Instagram")
                raw_path, raw_title, raw_desc = download_reel(url)
                if not raw_path: continue
                
                # 2. Process (FFmpeg)
                status.update(progress=50, step="Scaling & Re-encoding (FFmpeg)")
                processed_path = process_video(raw_path)
                
                # 3. AI Metadata
                status.update(progress=70, step="Generating Viral AI Captions")
                final_title, final_desc = generate_ai_metadata(raw_title, raw_desc)
                
                # 4. Upload
                status.update(progress=85, step="Uploading to YouTube Shorts")
                upload_to_youtube(youtube, processed_path, final_title, final_desc, args.privacy)
                
                # 5. Save State & Cleanup
                status.mark_upload()
                save_completed_url(url)
                
                if os.path.exists(processed_path): os.remove(processed_path)
                if os.path.exists(raw_path): os.remove(raw_path)
                
                status.update(action="Finished", progress=100, step=f"Successfully posted!")
                status.log(f"✅ Posted: {final_title}")

            except Exception as e:
                status.log(f"❌ Error during processing: {e}")

        if not args.daily:
            break
        
        status.update(action="Sleeping", progress=0, step="Waiting for 24h")
        status.log("😴 Cycle complete. See you in 24 hours.")
        time.sleep(24 * 3600)

def main():
    parser = argparse.ArgumentParser(description="Instagram Reel to YouTube Shorts Agent (DASHBOARD MODE)")
    parser.add_argument("--file", default="reel_urls.txt", help="Path to Reel URLs")
    parser.add_argument("--daily", action="store_true", help="Post daily logic")
    parser.add_argument("--limit", type=int, default=1, help="Number of videos per run")
    parser.add_argument("--privacy", default="unlisted", choices=["public", "private", "unlisted"], help="Upload visibility")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    
    args = parser.parse_args()

    # Start the automation loop in a background thread
    bot_thread = threading.Thread(target=run_automation_loop, args=(args,), daemon=True)
    bot_thread.start()

    # Start the FastAPI web server
    import uvicorn
    status.log(f"🌐 Dashboard available on port {args.port}")
    uvicorn.run(app, host="0.0.0.0", port=args.port)

if __name__ == "__main__":
    main()
