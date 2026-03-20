import threading

try:
    from win11toast import toast
    TOAST_AVAILABLE = True
except ImportError:
    TOAST_AVAILABLE = False


class NotificationManager:
    def __init__(self, log_callback=None):
        self.log_callback = log_callback
        self.available = TOAST_AVAILABLE

    def log(self, message):
        if self.log_callback:
            self.log_callback(message)

    def show_notification(self, title, message, duration=5):
        if not self.available:
            self.log(f"Notification (toast unavailable): {title} - {message}")
            return

        try:
            def show_toast_async():
                try:
                    duration_str = 'short' if duration <= 5 else 'long'
                    toast(title, message, duration=duration_str)
                except Exception as e:
                    self.log(f"Notification error: {str(e)}")

            thread = threading.Thread(target=show_toast_async, daemon=True)
            thread.start()

        except Exception as e:
            self.log(f"Could not show notification: {str(e)}")

    def is_available(self):
        return self.available
