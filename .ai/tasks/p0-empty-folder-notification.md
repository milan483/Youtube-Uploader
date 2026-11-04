# P0: Prevent repeated empty watch-folder notifications

- **Status:** Implemented; awaiting independent review
- **Priority:** P0
- **Target branch:** main
- **Working branch:** fix/p0-empty-folder-notification
- **Owner:** Codex implementation; ChatGPT review

## Objective

Stop the watch-folder notification from appearing repeatedly while the folder remains empty. Treat it as a state transition, not a message emitted on every polling cycle.

## Repository evidence

The current implementation has this call path:

1. controllers/watch_controller.py — WatchController._watch_folder_worker() repeatedly invokes _perform_folder_check().
2. controllers/watch_controller.py — the local on_no_files() callback inside _perform_folder_check() unconditionally emits notify_empty.
3. services/batch_uploader.py — BatchUploader.upload_folder() calls on_no_files whenever FileHandler.get_video_files(folder_path) returns no supported video files.
4. config.py — WATCH_FOLDER_POLL_INTERVAL is 30 seconds.
5. gui.py — the notify_empty callback checks the existing notify_when_empty preference and displays the toast.

Manual force checks also call _perform_folder_check(), so the deduplication must live in the controller and be shared by periodic and manual checks.

## Required behavior

1. Do not display an empty-folder notification merely because watching starts and the first scan finds no supported videos.
2. When a scan discovers one or more supported videos, arm one empty-state notification for the currently selected watch folder.
3. If a later scan finds no supported videos, emit notify_empty once and mark that empty transition as already notified.
4. Further empty scans must not emit another notification.
5. If a later scan discovers supported videos again, re-arm the notification. The next transition to no supported videos may emit one new notification.
6. Changing the selected watch-folder path resets the state for the newly selected folder. Normalize paths consistently when comparing them.
7. Automatic polling and manual force checks must share the same deduplication state.
8. Preserve the existing notify_when_empty preference, callback contract, polling interval, upload behavior, retry behavior, cooldown behavior, and cancellation behavior.

The current GUI message says “Watch folder is empty - all videos uploaded!” but the batch layer only establishes that no supported video files were found; it cannot prove that every file was uploaded successfully. Change this message to neutral, accurate wording such as “No supported videos found in watch folder.” Do not change the preference name or notification title unless necessary.

## Implementation guidance

- Keep the state in WatchController, not in the GUI notification callback or BatchUploader.
- Use a small explicit state (for example, whether supported content has been observed since the last empty notification, associated with the normalized watch-folder path).
- Reset/re-arm the state when on_batch_found(total_files) reports a positive count.
- Avoid races between folder changes and checks; retain the existing non-blocking _check_lock behavior.
- Do not introduce a dependency or redesign the watcher.

## Regression tests

Extend tests/test_watch_controller.py to cover:

- Initial empty scan does not emit notify_empty.
- Repeated empty scans after startup still emit no notification until supported content has been observed.
- A supported-video scan followed by an empty scan emits exactly one notification.
- Consecutive empty scans after that transition do not emit additional notifications.
- A new supported-video scan re-arms the notification; the next empty scan emits exactly one more.
- Changing the watch-folder path resets the state; an initially empty new folder does not inherit the previous folder's state.
- Periodic and manual checks share the same state because both use _perform_folder_check().

Use the existing fakes and callback pattern where practical. Keep tests deterministic; do not rely on real sleeps, network access, or live YouTube API calls.

## Out of scope

- Recursive directory scanning.
- Uploaded-folder management or clip deletion.
- Linux notification/tray implementation.
- SSL retry or resumable-upload changes.
- Quota-model changes.
- General GUI or architecture refactoring.
- Changes to unrelated notification types.

## Verification

Run:

    python -m pytest tests/test_watch_controller.py -q
    python -m pytest -q

Report the exact results. If the full suite cannot run, state why and distinguish verified tests from unverified behavior.

## Completion record

- **Implementation status:** Complete within P0 scope. Controller-owned state suppresses startup empties, arms on supported content, emits once on a later empty scan, and resets on normalized folder changes. A folder-selection generation prevents stale scan callbacks from affecting a new selection. The existing non-blocking check lock and notification preference are preserved. The toast now says “No supported videos found in watch folder.”
- **Changed files:** controllers/watch_controller.py, gui.py, tests/test_watch_controller.py, and this completion record.
- **Focused test result:** Passed, exit 0: `/tmp/youtube-uploader-p0-venv/bin/python -m pytest tests/test_watch_controller.py -q` (9 passed in 0.02s).
- **Full test result:** Passed, exit 0: `/tmp/youtube-uploader-p0-venv/bin/python -m pytest -q` (35 passed in 0.04s). `git diff --check` also passed, exit 0.
- **Environment:** Initial system-Python commands (`python -m pytest tests/test_watch_controller.py -q` and `python -m pytest -q`) failed, exit 1, because pytest was absent. Validation then used an external temporary virtual environment with pytest and requests installed; no project dependencies were changed. Existing test stubs replace unavailable Google API modules.
- **Commit:** Implementation: `5b776518e01ee67c81ee4656376de26e6f73278a`. The PR implementation report records the final documentation-inclusive head.
- **Pull request:** https://github.com/milan483/Youtube-Uploader/pull/1 (existing draft).
- **Known limitations:** No Windows GUI/toast smoke test or live YouTube upload was performed. Tests use deterministic fakes without network access. No CI checks were reported before push; final CI status is recorded in the PR report. Independent review remains pending.
