import os
import time
from core.status import status_manager

class AutomationWorkflow:
    def __init__(self, downloader, processor, ai_agent, youtube_service, config):
        self.downloader = downloader
        self.processor = processor
        self.ai_agent = ai_agent
        self.youtube_service = youtube_service
        self.config = config

    def load_completed_urls(self):
        if os.path.exists(self.config['completed_urls_file']):
            with open(self.config['completed_urls_file'], 'r') as f:
                return set(line.strip() for line in f if line.strip())
        return set()

    def save_completed_url(self, url):
        with open(self.config['completed_urls_file'], 'a') as f:
            f.write(url + "\n")

    def run(self):
        status_manager.is_running = True
        status_manager.log("🚀 Automation Workflow Starting")
        
        try:
            youtube = self.youtube_service.get_authenticated_service()
        except Exception as e:
            status_manager.log(f"❌ YouTube Auth Failed: {e}")
            status_manager.is_running = False
            return

        while True:
            status_manager.update(action="Checking URLs", progress=10, step="Scanning File")
            completed_urls = self.load_completed_urls()
            
            if not os.path.exists(self.config['urls_file']):
                status_manager.update(action="Waiting for file", progress=0, step="Idle")
                if not self.config['daily']: break
                time.sleep(60)
                continue

            with open(self.config['urls_file'], 'r') as f:
                all_urls = [line.strip() for line in f if line.strip()]

            new_urls = [u for u in all_urls if u not in completed_urls]
            
            if not new_urls:
                status_manager.update(action="No new URLs", progress=0, step="Idle")
                if not self.config['daily']: break
                status_manager.update(action="Sleeping", step="Waiting for 1 hour")
                time.sleep(3600)
                continue

            batch = new_urls[:(1 if self.config['daily'] else self.config['limit'])]

            for url in batch:
                try:
                    # 1. Download
                    raw_path, raw_title, raw_desc = self.downloader.download_reel(url)
                    if not raw_path: continue
                    
                    # 2. Process
                    processed_path = self.processor.process_video(raw_path)
                    
                    # 3. AI Metadata
                    final_title, final_desc = self.ai_agent.generate_viral_metadata(raw_title, raw_desc)
                    
                    # 4. Upload
                    self.youtube_service.upload_video(processed_path, final_title, final_desc, self.config['privacy'])
                    
                    # 5. Cleanup
                    status_manager.mark_upload()
                    self.save_completed_url(url)
                    
                    if os.path.exists(processed_path): os.remove(processed_path)
                    if os.path.exists(raw_path): os.remove(raw_path)
                    
                    status_manager.update(action="Idle", progress=100, step=f"Successfully posted!")
                    status_manager.log(f"✅ Posted: {final_title}")

                except Exception as e:
                    status_manager.log(f"❌ Automation Error: {e}")

            if not self.config['daily']:
                break
            
            # Scheduling for next run
            import pytz
            from datetime import datetime, timedelta
            
            # Use TIMEZONE from env or default to UTC
            tz_str = os.getenv("TIMEZONE", "UTC")
            try:
                timezone = pytz.timezone(tz_str)
            except Exception:
                timezone = pytz.utc
                status_manager.log(f"⚠️ Invalid TIMEZONE '{tz_str}', defaulting to UTC")
            
            now = datetime.now(timezone)
            target_time_str = self.config.get('post_time', '02:00')
            target_h, target_m = map(int, target_time_str.split(':'))
            
            target = now.replace(hour=target_h, minute=target_m, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            
            wait_seconds = (target - now).total_seconds()
            hours_wait = wait_seconds / 3600
            
            status_manager.update(action="Sleeping", progress=0, step=f"Next post at {target.strftime('%H:%M')} ({tz_str})")
            status_manager.log(f"😴 Cycle complete. See you at {target.strftime('%Y-%m-%d %H:%M:%S %Z')} ({hours_wait:.1f} hours away)")
            time.sleep(wait_seconds)
