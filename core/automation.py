import os
import json
import random
import time
from datetime import date
from core.status import status_manager

# Path to the file that persists which channel posted last.
CHANNEL_STATE_FILE = os.path.join(
    "/app/data" if os.path.exists("/app/data") else ".",
    "channel_state.json"
)

class AutomationWorkflow:
    def __init__(self, downloader, processor, ai_agent, youtube_service, config,
                 youtube_service_ch2=None):
        self.downloader = downloader
        self.processor = processor
        self.ai_agent = ai_agent
        self.youtube_service = youtube_service          # Channel 1
        self.youtube_service_ch2 = youtube_service_ch2  # Channel 2 (optional)
        self.config = config

    # ------------------------------------------------------------------
    # Channel-state helpers
    # ------------------------------------------------------------------

    def _load_channel_state(self):
        """Return the persisted channel state dict, or a safe default."""
        if os.path.exists(CHANNEL_STATE_FILE):
            try:
                with open(CHANNEL_STATE_FILE, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"last_channel": 0, "last_post_date": ""}

    def _save_channel_state(self, channel_number):
        """Persist the channel that just posted and today's date."""
        state = {"last_channel": channel_number, "last_post_date": str(date.today())}
        try:
            with open(CHANNEL_STATE_FILE, 'w') as f:
                json.dump(state, f)
        except Exception as e:
            status_manager.log(f"⚠️ Could not save channel state: {e}")

    def _determine_channel(self):
        """
        Decide which channel should post today.

        Rules:
        - If we already posted today → return None (skip).
        - If last_channel was 1 (or unknown) → use 2 (if available) else 1.
        - If last_channel was 2 → use 1.
        - If channel 2 service is not configured → always use 1.
        """
        state = self._load_channel_state()
        today = str(date.today())

        if state.get("last_post_date") == today:
            status_manager.log("⏭️ Already posted today — skipping this cycle.")
            return None

        last = state.get("last_channel", 0)

        if self.youtube_service_ch2 is None:
            # No second channel configured; always use channel 1.
            return 1

        if last == 1:
            return 2
        else:
            # last == 2, or 0 (first ever run) → start with channel 1
            return 1

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

        # Pre-authenticate both channels so we fail fast on bad credentials.
        try:
            self.youtube_service.get_authenticated_service()
            status_manager.log("✅ Channel 1 authenticated")
        except Exception as e:
            status_manager.log(f"❌ YouTube Auth Failed (Channel 1): {e}")
            status_manager.is_running = False
            return

        if self.youtube_service_ch2 is not None:
            try:
                self.youtube_service_ch2.get_authenticated_service()
                status_manager.log("✅ Channel 2 authenticated")
            except Exception as e:
                status_manager.log(f"⚠️ YouTube Auth Failed (Channel 2): {e} — will use Channel 1 only")
                self.youtube_service_ch2 = None

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

            # --- Determine which channel posts this cycle ---
            if self.config['daily']:
                channel_number = self._determine_channel()
                if channel_number is None:
                    # Already posted today; sleep until next scheduled time.
                    pass  # fall through to the scheduling block below
                else:
                    active_service = (
                        self.youtube_service_ch2
                        if channel_number == 2
                        else self.youtube_service
                    )
                    status_manager.log(f"📺 Today's channel: Channel {channel_number}")

                    # Randomly select 1 URL from new URLs
                    batch = [random.choice(new_urls)] if new_urls else []
                    if batch:
                        remaining = len(new_urls) - 1
                        status_manager.log(
                            f"🎲 Selected random URL: {batch[0]} "
                            f"({remaining} URLs remaining)"
                        )

                    for url in batch:
                        try:
                            # 1. Download
                            raw_path, raw_title, raw_desc = self.downloader.download_reel(url)
                            if not raw_path: continue

                            # 2. Process (codec varies by channel)
                            processed_path = self.processor.process_video(
                                raw_path, channel_number=channel_number
                            )

                            # 3. AI Metadata (style varies by channel)
                            final_title, final_desc = self.ai_agent.generate_viral_metadata(
                                raw_title, raw_desc, channel_number=channel_number
                            )

                            # 4. Upload to the active channel
                            active_service.upload_video(
                                processed_path, final_title, final_desc,
                                self.config['privacy']
                            )

                            # 5. Persist state & cleanup
                            self._save_channel_state(channel_number)
                            status_manager.mark_upload()
                            self.save_completed_url(url)

                            if os.path.exists(processed_path): os.remove(processed_path)
                            if os.path.exists(raw_path): os.remove(raw_path)

                            status_manager.update(
                                action="Idle", progress=100,
                                step=f"Successfully posted to Channel {channel_number}!"
                            )
                            status_manager.log(
                                f"✅ Posted to Channel {channel_number}: {final_title}"
                            )
                            break  # Only one video per daily cycle

                        except Exception as e:
                            status_manager.log(f"❌ Automation Error: {e}")
            else:
                # Non-daily mode: process a batch using Channel 1 only.
                batch = new_urls[:self.config['limit']]
                for url in batch:
                    try:
                        raw_path, raw_title, raw_desc = self.downloader.download_reel(url)
                        if not raw_path: continue

                        processed_path = self.processor.process_video(raw_path, channel_number=1)
                        final_title, final_desc = self.ai_agent.generate_viral_metadata(
                            raw_title, raw_desc, channel_number=1
                        )
                        self.youtube_service.upload_video(
                            processed_path, final_title, final_desc,
                            self.config['privacy']
                        )

                        status_manager.mark_upload()
                        self.save_completed_url(url)

                        if os.path.exists(processed_path): os.remove(processed_path)
                        if os.path.exists(raw_path): os.remove(raw_path)

                        status_manager.update(action="Idle", progress=100, step="Successfully posted!")
                        status_manager.log(f"✅ Posted: {final_title}")

                    except Exception as e:
                        status_manager.log(f"❌ Automation Error: {e}")

                break  # Exit loop after non-daily batch

            # Scheduling for next run (daily mode only)
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
