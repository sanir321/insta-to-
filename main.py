import os
import time
import base64
import argparse
import threading
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import uvicorn

from core.status import status_manager
from core.downloader import Downloader
from core.processor import VideoProcessor
from core.automation import AutomationWorkflow
from services.ai_agent import AIAgent
from services.youtube_api import YouTubeService

# Load environment variables
load_dotenv()

# --- CONFIGURATION ---
DATA_DIR = "/app/data" if os.path.exists("/app/data") else "."
CLIENT_SECRETS_FILE = "client_secret.json"
TOKEN_PICKLE_FILE = os.path.join(DATA_DIR, "youtube_token.pickle")
COMPLETED_URLS_FILE = os.path.join(DATA_DIR, "completed_reels.txt")
DOWNLOAD_DIR = os.path.join(DATA_DIR, "downloads")

for folder in [DOWNLOAD_DIR]:
    os.makedirs(folder, exist_ok=True)

# --- SECRETS DECODER ---
def setup_headless_secrets():
    if not os.path.exists(CLIENT_SECRETS_FILE) and os.getenv("GOOGLE_CLIENT_SECRET_B64"):
        status_manager.log("🔓 Decoding Secret from env...")
        with open(CLIENT_SECRETS_FILE, "wb") as f:
            f.write(base64.b64decode(os.getenv("GOOGLE_CLIENT_SECRET_B64")))
    if not os.path.exists(TOKEN_PICKLE_FILE) and os.getenv("YOUTUBE_TOKEN_B64"):
        status_manager.log("🔓 Decoding Token from env...")
        with open(TOKEN_PICKLE_FILE, "wb") as f:
            f.write(base64.b64decode(os.getenv("YOUTUBE_TOKEN_B64")))

setup_headless_secrets()

# --- WEB SETUP ---
app = FastAPI(title="InstaToYT Automation Agent")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/api/status")
async def get_status():
    return JSONResponse(content=status_manager.to_dict())

@app.get("/health")
async def health():
    return {"status": "ok", "bot_running": status_manager.is_running}

# --- MAIN ENTRY ---
def main():
    parser = argparse.ArgumentParser(description="InstaToYT Agent - Premium Dashboard")
    parser.add_argument("--file", default="reel_urls.txt", help="Path to Reel URLs")
    parser.add_argument("--daily", action="store_true", help="Post daily logic")
    parser.add_argument("--limit", type=int, default=1, help="Number of videos per run")
    parser.add_argument("--privacy", default="unlisted", choices=["public", "private", "unlisted"], help="Upload visibility")
    parser.add_argument("--time", default="02:00", help="Daily post time (HH:MM)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    
    args = parser.parse_args()

    # Initialize Services
    downloader = Downloader(DOWNLOAD_DIR)
    processor = VideoProcessor()
    ai_agent = AIAgent(os.getenv("KILO_API_KEY"), os.getenv("KILO_MODEL", "deepseek/deepseek-chat"))
    youtube_service = YouTubeService(
        CLIENT_SECRETS_FILE, 
        TOKEN_PICKLE_FILE, 
        ["https://www.googleapis.com/auth/youtube.upload"]
    )

    config = {
        'urls_file': args.file,
        'completed_urls_file': COMPLETED_URLS_FILE,
        'daily': args.daily,
        'post_time': args.time,
        'limit': args.limit,
        'privacy': args.privacy
    }

    workflow = AutomationWorkflow(downloader, processor, ai_agent, youtube_service, config)

    # Start Workflow in Background
    def start_workflow():
        status_manager.log("⏳ Waiting 10s for web server to stabilize...")
        time.sleep(10)
        workflow.run()

    bot_thread = threading.Thread(target=start_workflow, daemon=True)
    bot_thread.start()

    # Run Server
    status_manager.log(f"🚀 Dashboard is active on port {args.port}")
    status_manager.log("👉 ACCESS PUBLICLY AT: [Your-Railway-Domain-URL]")
    status_manager.log("   (Check the 'Networking' section in Railway to find your domain!)")
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")

if __name__ == "__main__":
    main()
