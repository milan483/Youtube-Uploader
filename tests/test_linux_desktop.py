import os
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import linux_integration
import notification_manager
import system_tray_manager
from auth.token_store import TokenStore
from storage.json_store import JsonStore
from storage.preferences_store import PreferencesStore
from window_manager import WindowManager


def test_json_store_creates_missing_xdg_parent(tmp_path):
    path = tmp_path / "new-parent" / "nested" / "state.json"
    JsonStore().atomic_write_json(str(path), {"ok": 1})
    assert path.read_text(encoding="utf-8").find('"ok"') >= 0


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes")
def test_token_file_written_atomically_with_owner_only_permissions(tmp_path):
    path = tmp_path / "config" / "youtube-uploader" / "token.pickle"
    store = TokenStore(token_file=str(path))
    store.save_credentials({"demo": True})
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert store.load_credentials() == {"demo": True}
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700


def test_linux_startup_entry_created_and_removed(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(
        linux_integration, "sys",
        SimpleNamespace(platform="linux", executable=sys.executable)
    )
    manager = linux_integration.LinuxIntegration()
    manager.add_to_startup()

    target = tmp_path / "autostart" / "youtube-uploader.desktop"
    assert target.is_file()
    content = target.read_text(encoding="utf-8")
    assert "Type=Application" in content
    assert "Exec=" in content and "main.py" in content
    assert manager.is_startup_available()

    manager.remove_from_startup()
    assert not target.exists()


def test_linux_notifications_use_argv_not_shell(monkeypatch):
    calls = []
    monkeypatch.setattr(
        notification_manager, "sys", SimpleNamespace(platform="linux")
    )
    monkeypatch.setattr(notification_manager.shutil, "which", lambda name: "/usr/bin/notify-send")

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stderr="")

    class ImmediateThread:
        def __init__(self, target, daemon=True):
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr(notification_manager.subprocess, "run", run)
    monkeypatch.setattr(notification_manager.threading, "Thread", ImmediateThread)

    manager = notification_manager.NotificationManager()
    assert manager.is_available()
    manager.show_notification("Title; echo bad", "Safe message", duration=2)

    assert len(calls) == 1
    assert calls[0][0][-2:] == ["Title; echo bad", "Safe message"]
    assert calls[0][0][0] == "notify-send"
    assert "shell" not in calls[0][1]


def test_wayland_tray_failure_leaves_safe_fallback(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    monkeypatch.setattr(system_tray_manager, "sys", SimpleNamespace(platform="linux"))
    manager = system_tray_manager.SystemTrayManager(lambda: None, lambda: None)

    def unavailable():
        raise ImportError("No GObject introspection bindings")

    monkeypatch.setattr(manager, "_setup_appindicator", unavailable)
    assert manager.setup() is False
    assert manager.is_available() is False


def test_window_never_withdraws_when_tray_is_unavailable():
    class FakeRoot:
        def __init__(self):
            self.operations = []

        def withdraw(self):
            self.operations.append("withdraw")

        def iconify(self):
            self.operations.append("iconify")

        def deiconify(self):
            self.operations.append("deiconify")

        def lift(self):
            self.operations.append("lift")

    class FakeTray:
        def is_available(self):
            return False

        def show(self):
            raise AssertionError("show must not be called")

        def hide(self):
            pass

    root = FakeRoot()
    manager = WindowManager(root, FakeTray())
    manager.minimize_to_tray()

    assert root.operations == ["iconify"]


def test_start_on_login_preference_rejects_nonboolean():
    store = PreferencesStore(json_store=object())
    assert store._validate_schema({"start_on_login": True})
    assert not store._validate_schema({"start_on_login": "yes"})


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux XDG directories")
def test_config_uses_xdg_paths_from_a_separate_process(tmp_path):
    app_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["XDG_CONFIG_HOME"] = str(tmp_path / "config")
    env["XDG_STATE_HOME"] = str(tmp_path / "state")
    env["XDG_DATA_HOME"] = str(tmp_path / "data")
    code = (
        "import config; "
        "print(config.USER_PREFERENCES_FILE); "
        "print(config.UPLOAD_HISTORY_FILE); "
        "print(config.ICON_PATH)"
    )
    output = subprocess.run(
        [sys.executable, "-c", code],
        cwd=app_root, env=env, capture_output=True, text=True, check=True
    ).stdout.splitlines()

    assert output[0] == str(tmp_path / "config" / "youtube-uploader" / "user_preferences.json")
    assert output[1] == str(tmp_path / "state" / "youtube-uploader" / "upload_history.json")
    assert output[2] == str(app_root / "assets" / "icon.png")
