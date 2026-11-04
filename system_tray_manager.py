"""Tray integration with a native AppIndicator backend on Linux Wayland."""
import os
import sys
import threading

import config


class SystemTrayManager:
    def __init__(self, on_show_callback, on_quit_callback, log_callback=None):
        self.on_show_callback = on_show_callback
        self.on_quit_callback = on_quit_callback
        self.log_callback = log_callback
        self.tray_icon = None
        self._indicator = None
        self._indicator_api = None
        self._gtk = None
        self._glib = None
        self._available = False

    def log(self, message):
        if self.log_callback:
            self.log_callback(message)

    def is_available(self):
        return self._available

    def setup(self):
        is_wayland = sys.platform.startswith("linux") and (
            os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
            or bool(os.environ.get("WAYLAND_DISPLAY"))
        )
        try:
            if is_wayland:
                return self._setup_appindicator()
            return self._setup_pystray()
        except Exception as error:
            self._available = False
            self.log(f"Tray unavailable (main window will remain accessible): {error}")
            return False

    def _setup_appindicator(self):
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk, GLib
        try:
            gi.require_version("AyatanaAppIndicator3", "0.1")
            from gi.repository import AyatanaAppIndicator3 as AppIndicator
        except (ImportError, ValueError):
            gi.require_version("AppIndicator3", "0.1")
            from gi.repository import AppIndicator3 as AppIndicator

        indicator = AppIndicator.Indicator.new(
            "youtube-uploader", "video-x-generic",
            AppIndicator.IndicatorCategory.APPLICATION_STATUS
        )
        menu = Gtk.Menu()
        for title, callback in (("Show", self._on_show_clicked),
                                ("Exit", self._on_quit_clicked)):
            item = Gtk.MenuItem(label=title)
            item.connect("activate", lambda _widget, cb=callback: cb())
            menu.append(item)
        menu.show_all()
        indicator.set_menu(menu)
        indicator.set_status(AppIndicator.IndicatorStatus.PASSIVE)

        self._indicator = indicator
        self._indicator_api = AppIndicator
        self._gtk = Gtk
        self._glib = GLib
        self._available = True
        threading.Thread(target=Gtk.main, daemon=True).start()
        self.log("Linux Wayland AppIndicator tray initialized")
        return True

    def _setup_pystray(self):
        from PIL import Image
        import pystray

        if os.path.exists(config.ICON_PATH):
            with Image.open(config.ICON_PATH) as loaded:
                icon_image = loaded.resize(
                    (config.TRAY_ICON_SIZE, config.TRAY_ICON_SIZE),
                    Image.Resampling.LANCZOS
                )
        else:
            icon_image = Image.new(
                "RGB", (config.TRAY_ICON_SIZE, config.TRAY_ICON_SIZE),
                color=config.FALLBACK_TRAY_ICON_COLOR
            )

        menu = pystray.Menu(
            pystray.MenuItem("Show", self._on_show_clicked),
            pystray.MenuItem("Exit", self._on_quit_clicked)
        )
        self.tray_icon = pystray.Icon(
            "youtube_uploader", icon_image, config.APP_NAME, menu
        )
        self.tray_icon.run_detached()
        self._available = True
        self.log("System tray icon initialized")
        return True

    def _on_show_clicked(self, icon=None):
        if self.on_show_callback:
            self.on_show_callback()

    def _on_quit_clicked(self, icon=None):
        if self.on_quit_callback:
            self.on_quit_callback()

    def show(self):
        if not self._available:
            return False
        try:
            if self._indicator is not None:
                self._indicator.set_status(self._indicator_api.IndicatorStatus.ACTIVE)
            elif self.tray_icon is not None:
                self.tray_icon.visible = True
            else:
                return False
            return True
        except Exception as error:
            self.log(f"Could not show tray icon: {error}")
            self._available = False
            return False

    def hide(self):
        try:
            if self._indicator is not None:
                self._indicator.set_status(self._indicator_api.IndicatorStatus.PASSIVE)
            elif self.tray_icon is not None:
                self.tray_icon.visible = False
        except Exception as error:
            self.log(f"Could not hide tray icon: {error}")

    def stop(self):
        self.hide()
        try:
            if self.tray_icon is not None:
                self.tray_icon.stop()
            if self._gtk is not None and self._glib is not None:
                self._glib.idle_add(self._gtk.main_quit)
        except Exception as error:
            self.log(f"Error stopping tray icon: {error}")
        finally:
            self._available = False
