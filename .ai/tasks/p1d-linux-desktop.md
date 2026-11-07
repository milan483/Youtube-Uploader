# P1D — Linux desktop compatibility

- **Status:** Implemented in GitHub; awaiting CI and interactive KDE Wayland testing
- **Branch:** feat/p1d-linux-desktop
- **Base:** main (P0 and P1A merged)
- **Reviewer:** ChatGPT / GitHub

## Implementation inventory

- `requirements.txt`: platform markers for Windows-only pywin32/win11toast/winshell, so `pip install -r requirements.txt` is viable on Linux.
- `config.py`: use XDG config/state locations on Linux, absolute icon resources, retain Windows legacy paths and a legacy project-root OAuth client JSON fallback.
- `storage/json_store.py`: create parent directories for atomic writes.
- `auth/token_store.py`: atomic token writes, POSIX owner-only file permissions (0600), secure directory creation; Windows ACL handling retained.
- `notification_manager.py`: native Linux `notify-send` backend, no unconditional Windows toast import.
- `system_tray_manager.py`: optional Ayatana AppIndicator for Wayland, pystray on Windows/X11, safe startup and teardown behavior.
- `window_manager.py`: iconify to the taskbar if no tray is available. Never withdraw the only visible launcher.
- `linux_integration.py`: XDG autostart creation/removal.
- `gui.py`: platform selection and Linux startup preference/label; marshal tray Show callback onto Tk thread.
- `main.py`: Linux CLI launcher for existing main.pyw.
- `tests/test_linux_desktop.py`: notifications, token modes, XDG paths, startup, safe tray fallback, preference validation.
- Windows/Linux pytest GitHub Actions workflow and existing platform-specific test corrections, reused from P1B.

## Required validation

```bash
python -m pytest tests/test_linux_desktop.py -q
python -m pytest -q
git diff --check
```

GitHub CI must pass on Windows and Ubuntu Python 3.11/3.13. Headless CI doesn't establish that GI and KDE's StatusNotifierWatcher cooperate, and no actual Plasma Wayland or Windows GUI smoke test was run by ChatGPT.

## KDE Wayland smoke checklist

1. Install Arch dependencies documented in README and activate a `--system-site-packages` virtualenv.
2. Launch via `python main.py` from a non-repository working directory. Verify icon load and no missing-state-directory errors.
3. Trigger a safe test notification with `notify-send` installed and check that it appears.
4. Enable Start on login, verify the XDG desktop file is created; disable it and verify it disappears.
5. Minimize to tray; test Show/Exit in KDE Plasma. If the indicator is unavailable, verify the app remains in the taskbar and is recoverable.
6. Verify new token permissions with `stat -c %a ~/.config/youtube-uploader/token.pickle` (should be 600).
7. Confirm Windows platform marker installation is skipped on Linux, while the Windows app remains functional.

## Limitations

- GTK AppIndicator is optional and may not work on every compositor; headless CI can only exercise safe fallback.
- The OAuth token is still stored in Python pickle. Owner-only permission helps limit access but does not protect against tampering by another process running as the same user.
- Linux state migration from older working-directory files is not automatic. Instructions are documented in README.
- The XDG desktop entry runs the interpreter used to create it; moving/deleting that virtualenv requires recreating the entry.

## Test record

Pending CI and manual smoke. No local clone was available to execute tests from ChatGPT.
