import os
from PIL import Image
import pystray
import config


class SystemTrayManager:
    def __init__(self, on_show_callback, on_quit_callback, log_callback=None):
        self.on_show_callback = on_show_callback
        self.on_quit_callback = on_quit_callback
        self.log_callback = log_callback
        self.tray_icon = None

    def log(self, message):
        if self.log_callback:
            self.log_callback(message)

    def setup(self):
        try:
            if os.path.exists(config.ICON_PATH):
                icon_image = Image.open(config.ICON_PATH)
                icon_image = icon_image.resize(
                    (config.TRAY_ICON_SIZE, config.TRAY_ICON_SIZE),
                    Image.Resampling.LANCZOS
                )
                self.log(f"Loaded tray icon from {config.ICON_PATH}")
            else:
                icon_image = Image.new(
                    'RGB',
                    (config.TRAY_ICON_SIZE, config.TRAY_ICON_SIZE),
                    color=config.FALLBACK_TRAY_ICON_COLOR
                )
                self.log(f"Using fallback tray icon ({config.FALLBACK_TRAY_ICON_COLOR} square)")

            menu = (
                pystray.MenuItem("Show", self._on_show_clicked),
                pystray.MenuItem("Exit", self._on_quit_clicked)
            )

            self.tray_icon = pystray.Icon(
                "youtube_uploader",
                icon_image,
                config.APP_NAME,
                menu
            )

            self.tray_icon.run_detached()
            self.log("System tray icon created")

        except Exception as e:
            self.log(f"Warning: Could not create system tray icon: {str(e)}")

    def _on_show_clicked(self, icon=None):
        if self.on_show_callback:
            self.on_show_callback()

    def _on_quit_clicked(self, icon=None):
        if self.on_quit_callback:
            self.on_quit_callback()

    def show(self):
        if self.tray_icon:
            self.tray_icon.visible = True

    def hide(self):
        if self.tray_icon:
            self.tray_icon.visible = False

    def stop(self):
        if self.tray_icon:
            try:
                self.tray_icon.visible = False
                self.tray_icon.stop()
            except Exception as e:
                self.log(f"Error stopping tray icon: {str(e)}")
