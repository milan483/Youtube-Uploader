"""Native cross-platform desktop notifications."""
import shutil
import subprocess
import sys
import threading

import config

if sys.platform == "win32":
    try:
        from win11toast import toast
    except ImportError:
        toast = None
else:
    toast = None


class NotificationManager:
    def __init__(self, log_callback=None):
        self.log_callback = log_callback
        self.backend = None
        if sys.platform == "win32" and toast is not None:
            self.backend = "windows"
        elif sys.platform.startswith("linux") and shutil.which("notify-send"):
            self.backend = "linux"
        self.available = self.backend is not None

    def log(self, message):
        if self.log_callback:
            self.log_callback(message)

    def show_notification(self, title, message, duration=5):
        if not self.available:
            self.log(f"Notification (desktop backend unavailable): {title} - {message}")
            return

        def notify():
            try:
                if self.backend == "windows":
                    toast(title, message, duration="short" if duration <= 5 else "long")
                elif self.backend == "linux":
                    completed = subprocess.run(
                        ["notify-send", "-a", config.APP_NAME, "-t",
                         str(max(1, int(duration)) * 1000), title, message],
                        check=False, timeout=8, capture_output=True, text=True
                    )
                    if completed.returncode:
                        self.log(f"Linux notification error: {completed.stderr.strip()}")
            except Exception as error:
                self.log(f"Notification error: {error}")

        threading.Thread(target=notify, daemon=True).start()

    def is_available(self):
        return self.available
