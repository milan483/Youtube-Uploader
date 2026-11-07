"""Window visibility with a safe fallback when no system tray is available."""


class WindowManager:
    def __init__(self, root, tray_manager=None, log_callback=None):
        self.root = root
        self.tray_manager = tray_manager
        self.log_callback = log_callback

    def log(self, message):
        if self.log_callback:
            self.log_callback(message)

    def minimize_to_tray(self):
        try:
            tray = self.tray_manager
            if tray and tray.is_available() and tray.show():
                self.root.withdraw()
                self.log("Minimized to system tray")
            else:
                # Never hide the only way to reopen the window under Wayland.
                self.root.iconify()
                self.log("Tray unavailable; minimized to taskbar instead")
        except Exception as error:
            self.log(f"Error minimizing to tray: {error}")
            self.root.iconify()

    def restore_from_tray(self):
        try:
            self.root.deiconify()
            self.root.lift()
            if self.tray_manager:
                self.tray_manager.hide()
        except Exception as error:
            self.log(f"Error restoring window: {error}")

    def show(self):
        self.restore_from_tray()

    def hide(self):
        self.minimize_to_tray()
