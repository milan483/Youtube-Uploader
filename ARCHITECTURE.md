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
5. `BatchUploader` calls `UploadManager.upload_video(...)` per file.
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
- Path validation helper exists (`FileHandler.validate_path`) but is not currently enforced in the watch/upload path.
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
