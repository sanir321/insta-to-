import os
from datetime import datetime

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
        if len(self.logs) > 30: self.logs.pop(0)

    def mark_upload(self):
        self.total_uploads += 1
        self.last_upload_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self):
        return {
            "current_action": self.current_action,
            "total_uploads": self.total_uploads,
            "last_upload_time": self.last_upload_time,
            "active_url": self.active_url,
            "progress": self.progress,
            "step_name": self.step_name,
            "is_running": self.is_running,
            "logs": self.logs
        }

status_manager = StatusManager()
