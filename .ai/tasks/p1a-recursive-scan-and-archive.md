# P1A — Recursive watch-folder scanning and centralized Uploaded archive

- **Status:** Ready for implementation
- **Priority:** P1, stage A
- **Implementer:** Codex Desktop
- **Reviewer:** ChatGPT through GitHub
- **Branch:** feat/p1-recursive-archive
- **PR:** https://github.com/milan483/Youtube-Uploader/pull/2 (existing draft, continue in place)
- **Base:** main (includes merged P0 notification fix)

## Objective

Add an opt-in option to scan nested directories and, after a successful upload, archive clips under a *single* Uploaded directory at the selected watch root, preserving relative subdirectories. Ensure archived videos are never rediscovered or uploaded again.

Example with watch root `C:/Clips`:

```text
C:/Clips/
  Rain World/clip.mp4
  Minecraft/clip.mp4
  loose.mp4
  Uploaded/                    # excluded from discovery
```

On success, move clips to:

```text
C:/Clips/Uploaded/
  Rain World/clip.mp4
  Minecraft/clip.mp4
  loose.mp4
```

When recursive scanning is disabled, preserve existing top-level-only discovery and archiving.

## Repository analysis and existing contracts

- `file_handler.py:FileHandler.get_video_files(directory_path)` currently lists `os.listdir`, returning sorted **basenames**; it does not recurse.
- `services/batch_uploader.py:BatchUploader.upload_folder()` treats these as names relative to `folder_path` and joins them with `os.path.join(folder_path, filename)`.
- `upload_manager.py:UploadManager.upload_video(filepath, progress_callback=None)` derives the Uploaded destination from `os.path.dirname(filepath)`. Without an explicit watch root, nested uploads would create `Game/Uploaded/` instead of one central archive.
- `utils/config_utils.py:get_uploaded_folder_path` returns `watch_root/Uploaded`.
- `file_handler.py:FileHandler.safe_move` supports same-volume rename and cross-volume copy/verification with collision suffixing. Preserve its no-data-loss behavior and avoid overwriting existing archived clips.
- `controllers/watch_controller.py` owns watch-folder selection, folder scanning, and P0 notification deduplication; manual and periodic checks share the same controller.
- `gui.py` owns watch settings and calls `WatchController.start(...)`; `state_manager.py:get_all_preferences` and `storage/preferences_store.py` own defaults and validation.
- `upload_manager.py:upload_files_from_folder()` is a second batch caller; preserve its existing behavior unless recursive scanning is explicitly requested.
- Existing pytest modules: `tests/test_file_handler.py`, `tests/test_batch_uploader.py`, `tests/test_upload_manager.py`, `tests/test_watch_controller.py`.

Inspect only additional code necessary to preserve these contracts.

## Design decisions

1. Add a visible **Scan subdirectories** toggle to the current watch-folder settings. Store it in preferences as a boolean, e.g. `scan_subdirectories`; default **false** for new and existing users to avoid unexpected uploads.
2. Keep current non-recursive output compatible with existing callers. For recursive discovery, represent discovered files as **paths relative to the selected watch root**, sorted deterministically. Root-level files remain plain basenames, so `os.path.join(root, relative_path)` continues to work. Make the scanner and batch contract explicit in documentation/tests.
3. Use a safe tree walk (e.g. `os.walk` with `followlinks=False`). Do not traverse directory symlinks, or accept file symlinks that resolve outside the watch root. Reject unsafe or escaping relative paths before uploading or archiving.
4. Exclude the managed root-level `Uploaded` directory and legacy nested directories named `Uploaded` from **every** recursive scan. On Windows, account for case-insensitive filesystem naming. Exclude hidden/staging upload artifacts as appropriate; retain current supported video extensions.
5. Propagate the selected watch root explicitly through the batch-to-upload call so watch-mode uploads archive to `<watch_root>/Uploaded/<relative_parent>/<filename>`. Keep manual single-file uploads backward-compatible: their existing sibling Uploaded-folder behavior must not unexpectedly change.
6. Reuse `safe_move` and its verification behavior. Never overwrite a previously archived clip; collision handling must remain safe even with repeated names or colliding timestamp suffixes. Only move the local clip after YouTube reports successful upload.
7. Persist and reload the new setting. Both periodic and Force Check Now must honor it; the P0 empty-notification state must still behave correctly with nested discovered videos.
8. Keep retry-state keys, upload history, progress callbacks, and playlist-add behavior compatible with existing data. Do not migrate existing archive folders automatically; document that older nested Uploaded directories remain in place and are excluded from scanning.
9. Prefer making the central archive safe for the later P1B manager: incomplete cross-volume copies must not masquerade as completed archived clips. Use a temporary/staging destination with safe finalization if necessary; retain the original on failure.

## Acceptance criteria

- A watch root with nested supported clips is found when scanning is enabled, including two same-named files in different subdirectories.
- With scanning disabled, only top-level videos are selected. Existing user preferences default to this mode.
- `Uploaded` trees (including legacy nested Uploaded directories), unsafe symlinks, and paths escaping the selected root are not selected.
- Successfully uploaded nested clips move into a single central Uploaded directory with their original relative parent directories preserved.
- Clips already archived are not scanned a second time.
- Identically named clips in different source subdirectories have distinct archive destinations. Collisions inside an archive destination do not overwrite files.
- On upload or move failure, originals are not deleted or misplaced. No network upload is attempted for untrusted/outside-root path entries.
- Manual Upload File... continues to work without requiring a watch-root argument.
- No accidental re-uploads, altered playlist semantics, changed retry schedules, or changed P0 notification cadence.
- No runtime dependency additions unless clearly justified and documented.

## Verification

Add focused deterministic tests for:

- Recursive versus non-recursive discovery, sort order, mixed extensions, deep nesting, and permission failures.
- Exclusion of both root-level and nested Uploaded folders, including legacy content.
- Symlink loops and symlinks pointing outside the watch root; prevent traversal/path escape.
- Watch-root-relative path propagation from FileHandler → BatchUploader → UploadManager.
- Central archive for duplicate basenames in different subdirectories, collision avoidance, move failure, and preserved originals.
- Existing manual single-file upload behavior.
- Toggle persistence and reload; verify periodic and manual checks use the same setting.
- P0 notification re-arm with nested clips.

Run:
```bash
python -m pytest tests/test_file_handler.py tests/test_batch_uploader.py tests/test_upload_manager.py tests/test_watch_controller.py -q
python -m pytest -q
git diff --check
```

Tests should not depend on OAuth credentials or real uploads. If GUI integration cannot be automated, provide exact manual Windows smoke steps and record them as unverified.

## Out of scope

- Uploaded Clips Manager UI, Trash/Recycle Bin operations, and any deletion (next P1B task).
- Playlist auto-selection based on subdirectory name.
- Automatic post-upload deletion.
- SSL/TLS retry and resumable-upload redesign, unrelated concurrency fixes, and general Linux platform support.
- Changing the scope of supported video file extensions.
- Automatic moving/migration of legacy nested Uploaded archives.
- Changes to P0 notification semantics beyond making new recursive results flow through the existing controller.

## Completion record (Codex fills in)

- **Status:**
- **Files changed:**
- **Focused tests:**
- **Full suite:**
- **Windows smoke test:**
- **Commit SHA:**
- **PR report:**
- **Limitations / follow-up:**
