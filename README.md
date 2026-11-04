# YouTube Uploader

A **modular, secure, and maintainable** Python desktop application that automatically uploads videos from a watched folder to your YouTube channel.

---

## Refactor Safety

This project includes an automated `pytest` suite for critical upload/state/orchestration behavior. Refactors should preserve behavior and keep public APIs stable.

### Automated Tests (Windows)

```bash
# from repo root
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install pytest
python -m pytest -q
```

Notes:
- These tests are intentionally API/network independent (unit-style with fakes/mocks).
- Keep using the manual smoke checklist below for end-to-end GUI/runtime verification.

### Smoke Checklist (Manual)
- Launch the app (no import errors)
- Upload a single video
- Verify logs and state files update

## Features

### Core Functionality
- **Automatic upload monitoring** - Watches a folder and uploads new videos automatically
- **Single file upload** - Upload individual videos without folder monitoring
- **Duplicate detection** - MD5 hash-based detection prevents re-uploading same content
- **Safe file handling** - Copy + verify + delete ensures no data loss
- **Crash recovery** - Interrupted uploads automatically retry on next start
- **Quota management** - 24-hour cooldown for watch-mode batches with automatic resume after quota exceeded
- **Playlist support** - Automatically add uploaded videos to selected playlist
- **System tray** - Minimize to tray and run in background
- **User preferences** - Remembers last-used settings across sessions

### Advanced Features
- **Retry mechanism** - Failed uploads automatically retry with exponential backoff (3 total attempts: initial + 2 retries)
- **File lock handling** - Robust retry logic for antivirus/slow disk situations
- **Hash caching** - Optimized to avoid redundant hash calculations
- **Client refresh + connection warmup** - Refreshes aging YouTube clients and verifies connectivity before folder batches
- **Chunked uploads** - Large files (>100MB) upload in 10MB chunks with progress tracking
- **File size validation** - Pre-upload check against YouTube's 256GB limit
- **Duplicate filename handling** - Re-uploading edited videos adds timestamp suffix
- **Playlist sorting** - Sort playlist videos alphabetically with quota cost estimation
- **Complete playlist pagination** - Fetches all playlists regardless of count
- **Playlist validation** - Detects and reports deleted playlists before upload
- **Category selection** - Choose video category from dropdown (Gaming, Education, etc.)

### Automation Features
- **Autonomous mode** - "Set and forget" operation with zero manual intervention
- **Auto-start watching** - Automatically begin monitoring on app launch
- **Start minimized** - Launch directly to system tray for silent operation
- **Start with Windows** - Add to Windows startup folder for boot-time launch
- **Comprehensive tooltips** - Every control has helpful explanations
- **Custom icon support** - Use your own icon for window and tray

### Toast Notifications
- **Upload succeeded** - Notification when video uploads successfully
- **Upload failed** - Alert when upload fails (enabled by default)
- **Quota exceeded** - Alert when API quota exceeded (enabled by default)
- **Batch complete** - Notification when all videos in batch uploaded
- **Folder empty** - Notification when watch folder is empty (enabled by default)

### Security & Reliability
- **Token file protection** - On Windows with `pywin32`, ACLs restrict OAuth tokens to owner-only access
- **Path validation helper** - `FileHandler.validate_path()` exists, but is not yet enforced in the watch/upload flow
- **Atomic writes** - State files use temp-file-then-rename to prevent corruption
- **JSON schema validation** - Protects against corrupted state files
- **No sensitive data in logs** - OAuth tokens never logged

---

## Project Structure

```
youtube_uploader/
├── main.pyw                # Application entry point
├── config.py               # Configuration constants
├── auth_manager.py         # YouTube authentication & API client
├── file_handler.py         # Safe file operations (MD5, copy, move)
├── state_manager.py        # JSON state persistence
├── upload_manager.py       # Upload logic & quota management
├── gui.py                  # Tkinter GUI & system tray
├── dialog_manager.py       # File dialogs and message boxes
├── notification_manager.py # Windows toast notifications
├── system_tray_manager.py  # System tray icon handling
├── window_manager.py       # Window minimize/restore helpers
├── windows_integration.py  # Windows startup/shutdown integration
├── requirements.txt        # Python dependencies
├── README.md              # This file
│
├── auth/                   # Auth components
│   ├── oauth_flow.py
│   ├── playlist_repository.py
│   ├── token_store.py
│   └── youtube_client_factory.py
├── controllers/            # Background controllers
│   └── watch_controller.py
├── network/                # Network utilities
│   └── connectivity.py
├── services/               # Service layer
│   ├── batch_uploader.py
│   └── playlist_service.py
├── storage/                # JSON state persistence stores
│   ├── json_store.py
│   ├── upload_history_store.py
│   ├── upload_state_store.py
│   ├── quota_state_store.py
│   ├── playlist_sort_store.py
│   └── preferences_store.py
├── utils/                  # Shared helpers
│   ├── config_utils.py
│   ├── logging.py
│   └── youtube_api.py
│
├── client_secrets.json     # Your OAuth credentials (YOU provide this)
├── token.pickle           # Generated after first auth (auto-created)
│
├── upload_history.json    # MD5 hashes of uploaded files (auto-created)
├── upload_state.json      # Upload state tracking (auto-created)
├── quota_state.json       # Quota cooldown tracking (auto-created)
├── playlist_sort_state.json # Playlist sorting resume state (auto-created)
└── user_preferences.json  # User settings and automation preferences (auto-created)
```

---

## Setup and Installation

### Prerequisites
- **Python 3.9+** (tested with 3.9, 3.10, 3.11)
- **Windows** (for full functionality; Linux/Mac have limited features)
- **Google Cloud account** (for YouTube API access)

### Step 1: Get Google API Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable **YouTube Data API v3**:
   - Navigate to **APIs & Services > Library**
   - Search for "YouTube Data API v3"
   - Click **Enable**
4. Create OAuth credentials:
   - Go to **APIs & Services > Credentials**
   - Click **Create Credentials > OAuth client ID**
   - Select **Desktop app** as application type
   - Click **Create**
5. Download the JSON file
6. Rename to `client_secrets.json`
7. Place in the project root directory

### Step 2: Install Python Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**Note**: If `pywin32` installation fails, try:
```bash
pip install pywin32==311 --upgrade
python venv\Scripts\pywin32_postinstall.py -install
```

### Step 3: First Run

**Easiest way**: Double-click `main.pyw` in your project folder. The app will launch without a console window.

**Alternative methods**:
```bash
# Run with console window (useful for debugging)
python main.pyw

# Run without console window (normal use)
pythonw main.pyw
```

**First-time authorization**:
1. A browser window will open
2. Log in with your Google account
3. Grant permissions to the app
4. Browser will show "The authentication flow has completed"
5. Return to the app (it will continue automatically)

This creates `token.pickle` for future sessions (no browser needed).

---

## How to Use

### Basic Workflow

1. **Start the application**:
   ```bash
   python main.pyw
   ```

2. **Configure settings** (saved automatically for next session):
   - Click **Browse** to select watch folder
   - Choose **Privacy** setting (private/unlisted/public)
   - Choose **Playlist** (or "No Playlist")
   - Choose **Video Category** (Gaming, Education, etc.)

3. **Configure automation** (optional):
   - Enable **Autonomous Mode** for fully automatic operation
   - Enable **Auto-start watching on launch** to skip manual start
   - Enable **Start minimized to tray** to launch silently
   - Enable **Start with Windows** to launch on boot
   - Enable **Notify when folder is empty** for completion alerts

4. **Start watching**:
   - Click **Start Watching** (or enable auto-start in Automation Settings)
   - App monitors folder continuously
   - Minimizes to system tray when window is closed

5. **Add videos**:
   - Copy video files (`.mp4`, `.mov`, `.avi`) to watch folder
   - App detects and uploads automatically
   - Successful uploads move to `Uploaded/` subfolder

6. **Monitor progress**:
   - Progress bar shows upload status
   - Log window shows detailed activity
   - Status bar shows current state
   - Windows notification when folder is empty (if enabled)

### Controls

- **Start Watching**: Begin monitoring watch folder
- **Stop**: Stop monitoring (current upload completes)
- **Force Check Now**: Immediately check for new videos
- **Upload File...**: Upload a single video without folder monitoring
- **Sort Playlist**: Sort selected playlist alphabetically by video title

### System Tray

Right-click the tray icon:
- **Show**: Restore window from tray
- **Exit**: Close application

---

## Automation Settings

The Automation Settings panel enables "set and forget" operation:

### Autonomous Mode
When enabled, this "master switch" automatically enables:
- Auto-start watching on launch
- Start minimized to tray

**Perfect for**: Fully hands-off operation. Enable this once, add to Windows startup, and forget about it.

### Auto-start Watching on Launch
App automatically begins monitoring the watch folder when it starts.

**Perfect for**: Skipping the manual "Start Watching" button click every time.

### Start Minimized to Tray
App launches directly to system tray without showing the main window.

**Perfect for**: Silent background operation without desktop clutter.

### Start with Windows
Creates a shortcut in the Windows startup folder and registers it with the Windows StartupApproved registry. App launches automatically when Windows boots.

**Perfect for**: Truly automatic operation - computer boots, app starts, uploads begin.

**Note**: Requires `pywin32` and `winshell` packages. After enabling, the app will appear in Task Manager's Startup tab. Restart Windows for changes to take effect.

**How it works**:
- Creates a direct shortcut to `main.pyw` in your Windows Startup folder
- Registers the shortcut in Windows registry (`StartupApproved\StartupFolder`)
- Ensures the shortcut appears in Task Manager and actually runs at boot
- Removes Zone.Identifier security flag to prevent Windows from blocking it

### Notify When Folder is Empty
Shows a Windows toast notification when all videos have been uploaded.

**Perfect for**: Knowing when you can add more videos without checking the app.

**Note**: Requires `win11toast` package.

### Setting Up Full Automation

For completely hands-off operation:

1. Configure your watch folder, privacy, playlist, and category
2. Enable **Autonomous Mode** (this enables auto-start + minimized startup)
3. Enable **Start with Windows**
4. Enable **Notify when folder is empty** (optional but helpful)
5. Restart your computer

From now on:
- Windows boots → App starts silently in tray
- App watches folder → Videos upload automatically
- You get notified when folder is empty
- No manual intervention required!

---

## Customization

### Custom Icon

You can replace the default icon with your own:

1. **Prepare your icon**:
   - Format: PNG with transparency
   - Size: 256x256 pixels (recommended)
   - Name it: `icon.png`

2. **Install the icon**:
   ```bash
   # Place your icon in the assets folder
   cp /path/to/your/icon.png assets/icon.png
   ```

3. **Restart the app** - Your icon will appear in:
   - Window title bar and taskbar
   - System tray notification area
   - Future `.exe` builds (when packaged)

**No icon file?** The app gracefully falls back to a simple red square.

---

## Configuration Options

### Privacy Settings
- **Private**: Only you can see the video
- **Unlisted**: Anyone with the link can see it
- **Public**: Anyone can find and watch it

### Video Categories
Choose from popular YouTube categories:
- Film & Animation
- Music
- Gaming
- Education
- Science & Technology
- Entertainment
- And more...

### Playlists
- Select from **all** your playlists (no 50-playlist limit)
- Videos are automatically added after upload
- "No Playlist" = don't add to any playlist
- **Playlist Sorting**: Sort playlist videos alphabetically by title
  - Useful for date-based filenames (e.g., "2025-01-15_clip.mp4")
  - Smart quota cost estimation before sorting
  - Resume capability if quota exceeded mid-sort

---

## File Size & Upload Performance

### File Size Limits
- **Maximum file size**: 256GB (YouTube's limit for verified accounts)
- **Pre-upload validation**: App checks file size before attempting upload
- **Error handling**: Clear error message if file exceeds limit

### Upload Performance
- **Small files (<100MB)**: Upload in single chunk
- **Large files (>100MB)**: Chunked uploads with 10MB chunks
- **Progress tracking**: Real-time progress updates during chunked uploads
- **Resumable uploads**: Network interruptions can be recovered
- **File lock handling**: Exponential backoff retry for locked files (max 5 attempts)
- **Hash optimization**: Files only hashed twice (down from three times)

### Duplicate File Handling
- **Original uploads**: Files moved to `Uploaded/` folder after success
- **Re-uploads (edited versions)**: Timestamp suffix added automatically
  - Example: `video.mp4` → `video_20250115_143025.mp4`
- **No data loss**: Original file preserved until copy is verified

---

## Data Integrity Guarantees

### File Safety
1. **Same-drive fast path**: File is published into `Uploaded/` without replacing an existing archive file, then removed from its source path
2. **Cross-drive/fallback path**: File is copied to a hidden staging file and hash-verified before publication in `Uploaded/`
3. **Delete original**: Original is deleted only after successful copy verification (with retry logic)
4. **On failure**: Original file is preserved

### State Persistence
- **Atomic writes**: State files use temp-file-then-rename
- **Crash recovery**: Interrupted uploads marked as 'pending' and retried
- **Validation**: Schema validation before loading state
- **Backups**: Malformed JSON files are backed up with a timestamp suffix (`.corrupt.<ts>`)
- **Schema-invalid payloads**: Invalid schema content is logged and reset to empty state
- **Retry tracking**: Failed uploads tracked with retry count and next retry time

### Duplicate Prevention
- **MD5 hashing**: Each file hashed before upload
- **History check**: Hash compared against upload history
- **Skip duplicates**: Already-uploaded files skipped automatically

---

## Quota Management

### YouTube Upload Quota
- **Limit**: ~10 videos per 24 hours (varies by account)
- **Detection**: Automatic via API error codes
- **Cooldown**: 24 hours + 5-minute buffer
- **Enforcement scope**: Cooldown gate is enforced by the background watch/batch loop

### Cooldown Behavior
When quota is exceeded:
1. App records exact timestamp
2. Stops watch-mode batch upload attempts
3. Displays next check time
4. Waits 24 hours 5 minutes
5. Automatically resumes watch-mode processing

Manual actions (`Upload File...`, playlist sort) can still call the API and may return quota errors while cooldown is active.

### Retry Logic
For failed uploads (non-quota errors):
- **Automatic retry**: 3 total attempts (initial + 2 retries)
- **Exponential backoff**: 1 min, then 2 min
- **Smart tracking**: Retry count and next retry time stored
- **Transient network fast-retry**: Connection-reset/timeout style errors get short-delay retries before normal backoff scheduling
- **Manual intervention**: Only required after all retries exhausted

---

## Troubleshooting

### "client_secrets.json not found"
- Download OAuth credentials from Google Cloud Console
- Rename to exactly `client_secrets.json`
- Place in same directory as `main.pyw`

### "Authentication failed"
- Check internet connection
- Check VPN if using one
- Delete `token.pickle` and re-authenticate
- Verify `client_secrets.json` is valid

### "Quota exceeded" too soon
- YouTube quota is per 24 hours, not per day
- Check exact time of last quota hit in `quota_state.json`
- Wait full 24 hours from that timestamp

### "Playlist no longer exists" error
- Selected playlist was deleted from YouTube
- Choose a different playlist from dropdown
- Or select "No Playlist"

### Upload fails repeatedly
- Check log window for specific error
- Failed uploads are attempted up to 3 total times (initial + 2 retries)
- Manual intervention is needed after those attempts are exhausted
- Check file permissions and disk space

### File locked errors
- App automatically retries with exponential backoff
- If persists after 5 attempts, check for:
  - Antivirus software locking files
  - Other programs accessing the file
  - Slow disk I/O or failing drive

### System tray icon doesn't appear
- Check if `pystray` is installed: `pip show pystray`
- Check if Pillow is installed: `pip show pillow`
- Run `python main.pyw` (not `pythonw`) to see errors

### Automation features not working
- **Start with Windows**: Requires `pywin32` and `winshell` packages
  - Install with: `pip install pywin32 winshell`
  - After enabling, verify the shortcut appears in Task Manager → Startup tab
  - If not appearing: Disable and re-enable the setting to recreate the shortcut
  - Restart Windows after enabling
  - The app registers itself in the Windows StartupApproved registry automatically
- **Notifications**: Requires `win11toast` package
  - Install with: `pip install win11toast`
  - Only works on Windows 10/11
  - Fixes WPARAM errors from the unmaintained win10toast library
- **Auto-start not working**: Check that watch folder is configured in preferences
  - App won't auto-start watching if no folder is set

### Settings not persisting between sessions
- Check if `user_preferences.json` exists in app directory
- Check file permissions (should be writable)
- Check log for "Could not save preference" errors
- If corrupted, delete `user_preferences.json` (will be recreated with defaults)

### App doesn't start minimized even when enabled
- Make sure you're using `main.pyw`
- Check "Start minimized to tray" checkbox is enabled
- System tray must be working for minimized start to work

---

## Security Best Practices

### Credential Protection
- Never commit `client_secrets.json` to git
- Never commit `token.pickle` to git
- `.gitignore` included for protection
- Token file ACL hardening is applied on Windows when `pywin32` is installed
- `token.pickle` is trusted local state and deserialized with Python `pickle`

### File Permissions
On Windows with `pywin32` available, `token.pickle` is set to owner-only access:
```
Owner: FULL_CONTROL
Everyone else: No access
```

### Network Security
- All API calls use HTTPS
- OAuth tokens refreshed automatically
- No credentials stored in logs

---

## State File Formats

### upload_history.json
```json
{
  "abc123def456...": {
    "filename": "video.mp4",
    "upload_date": "2025-10-22T14:30:00",
    "video_id": "dQw4w9WgXcQ"
  }
}
```

### upload_state.json
```json
{
  "C:/Videos/video.mp4": {
    "state": "failed",
    "timestamp": "2025-10-22T14:30:00",
    "retry_count": 1,
    "next_retry_time": "2025-10-22T14:31:00"
  }
}
```

### quota_state.json
```json
{
  "last_quota_hit": "2025-10-22T14:30:00"
}
```

### playlist_sort_state.json
```json
{
  "playlist_id": "PLxxxxxxxxxxxxxxxx",
  "sorted_items": [
    {
      "id": "UEx4eHh4eHh4eHh4eHh4",
      "video_id": "dQw4w9WgXcQ",
      "title": "2025-01-15_clip.mp4",
      "snippet": {}
    }
  ],
  "last_position": 42
}
```

### user_preferences.json
```json
{
  "last_watch_folder": "C:/Videos/ToUpload",
  "scan_subdirectories": false,
  "privacy_setting": "unlisted",
  "playlist_title": "My Gaming Clips",
  "video_category": "Gaming",
  "autonomous_mode": true,
  "auto_start_watching": true,
  "start_minimized": true,
  "notify_when_empty": true,
  "auto_close_when_empty": false,
  "start_with_windows": true,
  "notify_upload_success": false,
  "notify_upload_failed": true,
  "notify_quota_exceeded": true,
  "notify_batch_complete": false
}
```

`scan_subdirectories` defaults to `false`, including for existing preferences that lack the field. Enable **Scan subdirectories** in the watch-folder settings to discover nested clips. Both periodic scans and **Force Check Now** use this setting. For example, `Clips/Game/clip.mp4` is archived as `Clips/Uploaded/Game/clip.mp4`; top-level clips still go directly into `Clips/Uploaded/`. Manual **Upload File...** keeps its sibling Uploaded-folder behavior.

Recursive discovery excludes dot-prefixed entries, file and directory symlinks, and every directory named `Uploaded` (case-insensitive). Older nested Uploaded archives stay where they are and are excluded from scanning. Archive collisions receive a unique suffix; existing archived clips are never overwritten. Failed copies retain the original and are not published as completed archive videos. No archive cleanup or deletion UI is included in this phase.

`auto_close_when_empty` is currently stored/validated as a preference but not yet enforced by runtime behavior.

---

## Development

See `ARCHITECTURE.md` for module boundaries, contracts, and refactor-safe extension guidance.

### Code Style
- PEP 8 compliant
- Comments should prioritize rationale for non-obvious behavior
- Public APIs and critical persistence/security paths are documented with docstrings
- Security considerations documented

### Module Architecture
- **Layered responsibilities** - UI (`gui.py`) orchestrates managers/services; auth/storage remain dedicated modules
- **State boundaries** - JSON persistence is implemented in `storage/*.py`; `state_manager.py` also owns retry gating, cooldown timing, playlist-sort resume, and preference defaults
- **Known coupling points** - `WatchController`, `BatchUploader`, and `UploadManager` collaborate through callback maps and shared `state_manager` method contracts
- **Extension guidance** - New behavior should be added in `services/`, `storage/`, or `utils/` before expanding GUI/controller code

### Internal Contracts
- **Watch callbacks (GUI -> WatchController)**: `set_progress`, `set_status`, `set_next_check`, `notify_empty`, `notify_upload_success`, `notify_upload_failed`, `notify_upload_error`, `notify_quota_exceeded`, `notify_batch_complete`
- **Batch callbacks (WatchController/UploadManager -> BatchUploader)**: `refresh_client`, `on_no_files`, `on_batch_found`, `on_batch_cancelled`, `on_batch_stopped`, `on_file_start`, `on_progress`, `on_file_result`, `on_file_error`, `on_quota_exceeded`, `warmup_connection`, `on_warmup_failed`
- **BatchUploader state contract**: when present, `upload_manager.state_manager` is expected to provide `get_upload_state`, `is_ready_for_retry`, and `get_retry_info`

### Contributing
- Fork the repository
- Create feature branch
- Make changes with tests
- Submit pull request

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

MIT License summary:
- Commercial use: Permitted
- Modification: Permitted
- Distribution: Permitted
- Private use: Permitted
- Liability and warranty disclaimers apply

---

## Credits

**Author**: Gerard
**Repository**: [GRardT/Youtube-Uploader](https://github.com/GRardT/Youtube-Uploader)

Built for personal workflow automation (daily gaming clip uploads).

---

## Support

For issues:
1. Check troubleshooting section above
2. Check logs in GUI window
3. Run with `python main.pyw` (not `pythonw`) to see console output
4. Check state files for corruption
5. Open an issue on GitHub

**Remember**: All your upload history and state files are in JSON format and human-readable. You can inspect or manually edit them if needed!


## Linux / KDE Plasma Wayland (P1D)

Core uploads and the Tkinter window can run on Linux. Windows-only Python dependencies are installed only on Windows. On Arch/CachyOS install the GTK AppIndicator integration and notification utility:

```bash
sudo pacman -S --needed python python-pip tk python-gobject libayatana-appindicator libnotify
python -m venv --system-site-packages .venv
source .venv/bin/activate.fish
python -m pip install -r requirements.txt
python main.py
```

The `--system-site-packages` option lets the virtual environment import the distro's `gi` bindings. The Linux Wayland tray uses AyatanaAppIndicator when available; otherwise minimizing falls back to the taskbar rather than hiding the only way to reopen the window. Notifications use `notify-send`. A **Start on login** checkbox manages an XDG autostart file in `~/.config/autostart`. Tray availability depends on the desktop's actual indicator support, which cannot be established by headless unit tests.

Linux application data follows XDG directories:
- Preferences and OAuth token: `$XDG_CONFIG_HOME/youtube-uploader` (default `~/.config/youtube-uploader`).
- History, retry and quota metadata: `$XDG_STATE_HOME/youtube-uploader` (default `~/.local/state/youtube-uploader`).
- The OAuth client JSON may be placed at `~/.config/youtube-uploader/client_secrets.json`, or supplied via `YOUTUBE_UPLOADER_CLIENT_SECRETS`. A legacy project-root `client_secrets.json` is also accepted.
- Previously stored tokens and state in the working directory are **not migrated automatically**. Copy trusted files to the corresponding XDG locations if migrating an existing Linux installation.

Token writes are atomic and owner-only (0600) on POSIX, but the existing pickle-based token file still assumes trusted local filesystem integrity. No automatic conversion to a new credential format is attempted. The `main.pyw` entry point remains available for Windows.


## Uploaded Clips Manager (P1B)

Select a watch folder and click **Uploaded Clips...** to browse the central `Uploaded/` archive recursively. The dialog lists root-relative filenames, sizes and total storage, with Refresh, Open Folder, Select All, Delete Selected and Delete All. Deletion confirmations show the count and selected file sizes. All deletions require confirmation and send **local archived copies** to the OS Trash/Recycle Bin using `send2trash`. They never delete YouTube videos or clear upload-history records.

The manager rejects symlinks, junctions, hidden/incomplete staging files and paths outside the selected archive. Deletion fails closed if Trash is unavailable; it never falls back to permanent removal. Same-process archiving and cleanup use a shared lock. Legacy per-subfolder Uploaded directories are not migrated or managed.

## Upload network recovery (P1C)

Uploads use the Google client's resumable `next_chunk()` interface, including one-chunk uploads. Transient failures such as SSL EOF are retried using the **same request/session** where possible, rather than restarting a new `videos.insert`. Exhausted retries are scheduled with persistent counters; successful uploads clear that retry metadata. Certificate verification failures are not classified as transient.

The upload session URI is not persisted across process restarts. Same-manager uploads are serialized, but independent application processes are not locked against duplicate uploads. Test unattended transfers with a disposable YouTube account.
