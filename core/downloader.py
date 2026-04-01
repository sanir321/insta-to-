import os
import yt_dlp
from core.status import status_manager

class Downloader:
    def __init__(self, download_dir):
        self.download_dir = download_dir

    def download_reel(self, url):
        status_manager.update(action="Downloading", progress=30, step="Downloading from Instagram", url=url)
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': os.path.join(self.download_dir, '%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)
                video_filename = ydl.prepare_filename(info_dict)
                title = info_dict.get('title', 'Instagram Reel')
                description = info_dict.get('description', '')
                
                if not os.path.exists(video_filename):
                    status_manager.log(f"❌ Downloaded content not found at {video_filename}")
                    return None, None, None
                
                status_manager.log(f"📥 Downloaded: {title}")
                return video_filename, title, description
        except Exception as e:
            status_manager.log(f"❌ Failed to download {url}: {e}")
            return None, None, None
