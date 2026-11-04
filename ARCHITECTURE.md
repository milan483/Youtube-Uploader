# Architecture Guide

This document describes the current runtime architecture, module boundaries, and internal contracts for the YouTube Uploader desktop application.

## Goals

- Keep upload behavior stable during refactors.
- Make cross-module contracts explicit.
- Document where business logic lives vs. where persistence/UI plumbing lives.

## Runtime Flow

1. `main.pyw` validates config, initializes managers, then starts GUI.
2. `AuthManager` initializes YouTube client and playlist cache.
3. GUI builds `WatchController` and wires callback maps.
4. `WatchController` runs polling loop and calls `BatchUploader`.
5. `BatchUploader` calls `UploadManager.upload_video(..., watch_root=folder_path)` per file.
6. `UploadManager` performs upload, retry/quota handling, playlist add, and safe move.
7. `StateManager` persists upload/quota/retry/preferences/sort state through `storage/*`.

## Layered Responsibilities

### Entry and Composition

- `main.pyw`
  - Composes all managers and the GUI.
  - Owns startup sequencing and fatal startup error handling.

### UI and Platform Integration

- `gui.py`
  - Owns Tkinter UI state, user actions, and notification preferences.
  - Owns callback map passed to `WatchController`.
  - Applies stored automation preferences on startup.
- `dialog_manager.py`
  - Message boxes and file/folder pickers.
- `system_tray_manager.py`, `window_manager.py`, `notification_manager.py`
  - Tray behavior, window visibility, toast notifications.
- `windows_integration.py`
  - Windows startup shortcut and `StartupApproved` registry integration.
  - Shutdown priority setup.

### Auth and API Client

- `auth_manager.py`
  - OAuth lifecycle, credential refresh, YouTube client lifecycle, playlist refresh.
- `auth/token_store.py`
  - Token persistence + Windows ACL hardening (best effort).
- `auth/oauth_flow.py`, `auth/youtube_client_factory.py`, `auth/playlist_repository.py`
  - Focused auth/client/playlist sub-operations.

### Upload and Orchestration

- `controllers/watch_controller.py`
  - Background polling loop, cooldown sleep behavior, batch-cycle orchestration.
- `services/batch_uploader.py`
  - Folder batch sequencing and per-file callback dispatch.
  - Retry deferral/exhaustion handling based on state metadata.
  - Maps upload outcomes into success/skip/fail counters using:
    - `upload_manager.QuotaExceededError` for quota-stop flow
    - skip-message classification in `utils/upload_utils.py`
- `upload_manager.py`
  - Core upload pipeline:
    - duplicate detection
    - upload execution
    - transient fast-retry vs. scheduled retry
    - quota detection/cooldown recording
    - playlist insertion
    - safe post-upload file move

### State and Persistence

- `state_manager.py`
  - In-memory state coordinator plus persistence adapter.
  - Owns retry gating logic, cooldown metadata, playlist-sort resume state, preference defaults.
- `storage/json_store.py`
  - Atomic JSON write and validated load behavior.
- `storage/*_store.py`
  - Per-file schema validation and save/load wrappers.

### File Safety and Utilities

- `file_handler.py`
  - Hashing, copy verification, safe move semantics, file operation retries.
- `utils/*`
  - Shared small helpers (`logging`, `youtube_api`, `config_utils`, `upload_utils`).
- `network/connectivity.py`
  - Internet connectivity wait loop used by auth flow.

## Internal Contracts

## WatchController Callback Contract (provided by GUI)

`WatchController` expects these callback keys:

- `set_progress(percent)`
- `set_status(message)`
- `set_next_check(message)`
- `notify_empty()`
- `notify_upload_success(filename)`
- `notify_upload_failed(filename, message)`
- `notify_upload_error(filename, error_message)`
- `notify_quota_exceeded()`
- `notify_batch_complete(summary)`

## BatchUploader Callback Contract

`BatchUploader.upload_folder(...)` supports these callback keys:

- `refresh_client()`
- `on_no_files()`
- `on_batch_found(total_files)`
- `on_batch_cancelled()`
- `on_batch_stopped(success_count, total_files)`
- `on_file_start(filepath, index, total_files)`
- `on_progress(current_index, total_files, percent)`
- `on_file_result(success, message, filepath, video_id)`
- `on_file_error(filepath, error)`
- `on_quota_exceeded()`
- `on_batch_complete(results)`
- `warmup_connection() -> bool`
- `on_warmup_failed()`

## Watch discovery and archive contract

- `FileHandler.get_video_files(directory_path, recursive=False)` returns sorted paths relative to the selected root. The default returns top-level basenames; recursive mode includes relative subdirectories.
- `BatchUploader.upload_folder(..., recursive=False)` validates discovered entries and propagates the watch root explicitly. Retry-state keys and per-file callback paths remain the joined source paths.
- `UploadManager.upload_video(filepath, progress_callback=None, watch_root=None)` archives watch batches beneath `<watch_root>/Uploaded/<relative_source_path>`. Without a watch root, manual single-file uploads retain sibling `Uploaded` behavior.
- Scanning excludes dot-prefixed files/directories, directory and file symlinks, and all directories named `Uploaded` (case-insensitive). Legacy nested archives remain in place and are excluded; no migration occurs.
- Source containment and archive ancestors are checked before upload and moving. Archive publication does not replace an existing file. Cross-volume copies use hidden staging files and are verified before publication; failed copies retain the source.
- `scan_subdirectories` is a persisted boolean, default false. The GUI transfers its value to the controller on the UI thread; periodic and manual checks snapshot the same plain controller setting.

## UploadManager/StateManager Contract

When available, `BatchUploader` assumes `upload_manager.state_manager` implements:

- `get_upload_state(filepath)`
- `is_ready_for_retry(filepath)`
- `get_retry_info(filepath)`

`UploadManager` additionally relies on:

- `get_retry_count(filepath)`
- `set_upload_state(...)`
- `is_file_uploaded(file_hash)`
- `add_upload_to_history(file_hash, filename, video_id)`
- `record_quota_hit()`
- `get_last_quota_hit()`

## Upload Outcome Classification Contract

- `BatchUploader` treats an upload as "skip" when message text matches
  `utils.upload_utils.is_skip_message(...)` (`already uploaded`, `retry scheduled`).
- Quota stop behavior relies on `UploadManager.upload_video(...)` raising
  `QuotaExceededError`, which `BatchUploader` catches to end the current batch.
- These are intentional implicit contracts and should be updated together if changed.

## State Files and Ownership

- `upload_history.json`
  - Owner: `UploadHistoryStore` + `StateManager`.
  - Purpose: duplicate prevention via file hash history.
- `upload_state.json`
  - Owner: `UploadStateStore` + `StateManager`.
  - Purpose: per-file state, retry count, next retry time.
- `quota_state.json`
  - Owner: `QuotaStateStore` + `StateManager`.
  - Purpose: last quota-hit timestamp.
- `playlist_sort_state.json`
  - Owner: `PlaylistSortStore` + `StateManager`/`PlaylistService`.
  - Purpose: interrupted sort resume.
- `user_preferences.json`
  - Owner: `PreferencesStore` + `StateManager`/`gui.py`.
  - Purpose: persisted UI/automation/notification settings.

Notes:

- Writes are atomic (temp file + replace/rename).
- Malformed JSON files are backed up with `.corrupt.<timestamp>`.
- Schema-invalid payloads are logged and treated as empty state.
- `scan_subdirectories` defaults to false for both new and existing preferences.
- `auto_close_when_empty` is currently persisted/validated but not enforced by runtime logic.

## Threading Model

- Tkinter UI runs on the main thread.
- Watch polling and uploads run on background threads.
- UI mutations from worker threads are routed through `root.after(...)` helpers.
- `WatchController` uses a lock to prevent overlapping folder checks.

## Security Boundaries and Assumptions

- OAuth tokens are persisted in `token.pickle`.
- `token.pickle` is loaded via Python `pickle`; this assumes trusted local file integrity.
- On Windows with `pywin32`, ACL hardening attempts owner-only access.
- Watch batches validate source containment and reject symlinks and archive entries before upload. Archive paths are checked for symlink redirection before upload and moving. These checks assume the local tree is not being maliciously replaced between checks and file operations.
- Logs should not include OAuth credentials/tokens.
- Quota cooldown gating is enforced by watch-mode batch flow; manual actions can still hit API quota errors.

## Extension Guidance

1. Prefer adding business logic to `services/` or `upload_manager.py` instead of GUI/controller code.
2. Keep persistence changes behind `storage/*_store.py` and `state_manager.py`.
3. Preserve callback keys and signatures unless all producers/consumers are updated together.
4. If adding new state fields, update:
   - corresponding store schema validator
   - README state schema section
   - this architecture document
5. If changing retry/cooldown behavior, update:
   - `upload_manager.py`
   - `state_manager.py`
   - user-facing docs (`README.md`)

## Refactor Safety Checklist

1. App launches without import/runtime startup errors.
2. Single file upload works end-to-end.
3. Folder watch batch uploads work end-to-end.
4. Quota cooldown gate blocks uploads and resumes after cooldown window.
5. Retry scheduling fields persist and are honored.
6. Preferences persist across restart (including automation and notification flags).
7. Playlist sorting works and resume state is cleared/saved correctly.


## Linux desktop integration (P1D)

- On Linux, `config.py` resolves XDG configuration/state directories and assets relative to the project, rather than relying on the current working directory.
- `JsonStore.atomic_write_json` creates missing parent directories before saving.
- `TokenStore.save_credentials` uses an atomic temporary file and owner-only POSIX permissions (0600). The token file remains a trusted-local-file pickle.
- `NotificationManager` uses native `notify-send` when available; the Windows toast backend is imported only on Windows.
- Under Wayland, `SystemTrayManager` attempts an Ayatana AppIndicator using GTK/GObject Introspection. It does not claim the icon is visible until a backend successfully initializes. If no usable tray backend exists, `WindowManager.minimize_to_tray` iconifies the window rather than withdrawing it.
- `LinuxIntegration` creates and removes an XDG autostart desktop file; `gui.py` selects the appropriate platform integration and persists `start_on_login` separately from the legacy Windows preference.
- `main.py` runs the existing `main.pyw` entry point for Linux. Windows startup remains unchanged.


## P1B local archive management

- `UploadedClipsManager` lists only supported video files under the selected watch root's central `Uploaded/`, rejecting hidden, symlinked, junction, and outside-root entries.
- The Tkinter `UploadedClipsDialog` owns confirmation and UI state; filesystem listing and Trash operations run off the Tk main thread and return per-file results.
- `FileHandler.archive_lock` serializes local archive moves with manager listing/deletion inside a single process. Cross-process filesystem races are outside this lock.
- Trash is delegated to `send2trash`; there is no permanent-delete fallback. Cleanup does not update StateManager or YouTube.

## P1C upload reliability

- UploadManager serializes each `upload_video` operation with a per-instance lock.
- Every upload uses a resumable `next_chunk` request. Transient errors retry the same request to retain library-managed upload URI and progress when available.
- StateManager preserves retry count across failed, uploading and pending state transitions; completion clears retry metadata.
- SSL EOF and connection resets are transient; certificate-verification errors are not.
- Resumable session offsets are not persisted across application restarts.
