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
            self.root.withdraw()
            if self.tray_manager:
                self.tray_manager.show()
            self.log("Minimized to system tray")
        except Exception as e:
            self.log(f"Error minimizing to tray: {str(e)}")

    def restore_from_tray(self):
        try:
            self.root.deiconify()
            self.root.lift()
            if self.tray_manager:
                self.tray_manager.hide()
        except Exception as e:
            self.log(f"Error restoring window: {str(e)}")

    def show(self):
        self.restore_from_tray()

    def hide(self):
        self.minimize_to_tray()
