"""Linux XDG autostart integration for Tkinter desktop sessions."""
import os
import sys
import tempfile
from pathlib import Path

import config


def _desktop_exec_quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'


class LinuxIntegration:
    def __init__(self, log_callback=None):
        self.log_callback = log_callback

    def log(self, message):
        if self.log_callback:
            self.log_callback(message)

    def is_startup_available(self):
        return sys.platform.startswith("linux")

    def setup_shutdown_handler(self):
        # Windows-only shutdown priority APIs have no Linux equivalent here.
        return

    def _autostart_path(self):
        config_root = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
        return config_root / "autostart" / "youtube-uploader.desktop"

    def add_to_startup(self):
        if not self.is_startup_available():
            raise RuntimeError("XDG autostart is only available on Linux")
        target = self._autostart_path()
        target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        command = f"{_desktop_exec_quote(sys.executable)} {_desktop_exec_quote(config.PROJECT_DIR / 'main.py')}"
        entry = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Version=1.0\n"
            f"Name={config.APP_NAME}\n"
            f"Exec={command}\n"
            f"Icon={config.ICON_PATH}\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n"
        )
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=target.parent,
                prefix=".youtube-uploader-", suffix=".desktop", delete=False
            ) as temp:
                temp_path = temp.name
                temp.write(entry)
                temp.flush()
                os.fsync(temp.fileno())
            os.chmod(temp_path, 0o600)
            os.replace(temp_path, target)
            self.log(f"Created XDG autostart entry: {target}")
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    def remove_from_startup(self):
        target = self._autostart_path()
        try:
            target.unlink()
            self.log(f"Removed XDG autostart entry: {target}")
        except FileNotFoundError:
            pass
