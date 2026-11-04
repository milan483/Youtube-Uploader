# P1A — Recursive watch-folder scanning and centralized Uploaded archive

- **Status:** Implemented; awaiting independent PR review
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

## Completion record

- **Status:** P1A implemented. P1B remains queued and was not implemented. Recursive discovery is opt-in and defaults off, including existing preferences. GUI setting changes are transferred to plain controller state on the UI thread and snapshotted for both periodic and manual checks.
- **Files changed:** `file_handler.py`, `services/batch_uploader.py`, `upload_manager.py`, `controllers/watch_controller.py`, `gui.py`, `state_manager.py`, `storage/preferences_store.py`; tests for file handler, batch uploader, upload manager, watch controller, state manager, and JSON schemas; `ARCHITECTURE.md`, `README.md`, this task record, and `codex_start_here.md` status.
- **Focused tests:** Passed, exit 0: `/tmp/youtube-uploader-p0-venv/bin/python -m pytest tests/test_file_handler.py tests/test_batch_uploader.py tests/test_upload_manager.py tests/test_watch_controller.py -q` — **49 passed in 2.62s**.
- **Full suite:** Passed, exit 0: `/tmp/youtube-uploader-p0-venv/bin/python -m pytest -q` — **63 passed in 2.59s**. `git diff --check` passed, exit 0. The external temporary virtual environment uses Python 3.14, pytest and requests; existing Google API test stubs avoid live network/API access. No runtime dependencies were added.
- **Development failures resolved:** An intermediate discovery test incorrectly assumed `.mkv` was supported (focused: 1 failed, 42 passed; full: 1 failed, 55 passed). Corrected the fixture to existing supported `.mov`; supported extensions are unchanged. Integration review caught and repaired consumed-source deletion in Windows rename fallback, duplicate publication after source-removal failure, and incomplete junction guards before final validation.
- **Windows smoke test:** Not run. See exact steps below. Automated tests exercise symlink safety on Linux, mock junction detection, and simulate Windows no-clobber rename; they do not constitute a real Windows filesystem or GUI test.
- **Commit SHA:** Implementation: `5c69fdaa247b6f7e779ec6d7b6c175bf22fa42f6`; the PR report records the final documentation-inclusive head.
- **PR report:** Posted to the existing draft [PR #2](https://github.com/milan483/Youtube-Uploader/pull/2); final head and report link are returned in the implementation response.
- **Limitations / follow-up:** Windows GUI, NTFS junction/permission behavior, and live YouTube smoke testing remain unverified. Static internal review found no remaining concrete blockers after repairs; independent ChatGPT PR review is still pending. CI status is recorded in the PR report. Local tree checks are repeated before upload/move but do not claim protection against malicious concurrent filesystem replacement. Legacy nested archives are excluded without migration. POSIX filesystems without hard-link support fail safe at publication, preserving the source. A crash can leave a hidden `.upload-staging-*.part` artifact; scanning excludes it. No P1B management, cleanup, or deletion UI is included.

### Implemented contracts and safety

Discovery returns sorted root-relative paths; non-recursive calls still return basenames. Hidden entries, Uploaded trees (case-insensitive), symlinks and junctions are excluded. Batch input is validated independently, including traversal/absolute/foreign-drive entries, then revalidated before per-file dispatch. Watch uploads pass the explicit root and revalidate both source and archive after the network operation. Manual uploads retain sibling Uploaded behavior, and the secondary folder caller retains its non-recursive default.

Successful watch uploads archive beneath the single root Uploaded directory with relative parents preserved. Publication never replaces an existing destination; repeated timestamp collisions receive an additional suffix. Cross-volume copies use reserved hidden staging and verification before no-clobber publication. Failed copies retain the original and clean up staging where possible. Source-deletion failures retry and attempt to remove the published duplicate, leaving the original. If archive movement fails after YouTube success, existing history/state semantics still record the successful upload and preserve the original to avoid an automatic duplicate upload.

### Windows smoke steps (not run)

Use a disposable watch directory and an authorized test YouTube account. Use distinct clip contents to avoid hash-based duplicate skipping.

1. Create `Clips/loose.mp4`, `Clips/Game A/clip.mp4`, `Clips/Game B/clip.mp4`, and `Clips/Game A/deep/extra.mov`. Put additional clips under both `Clips/Uploaded/` and `Clips/Game A/Uploaded/`, plus a dot-prefixed staging directory. Create a directory junction to an outside clip tree and a loop junction in this disposable tree.
2. Start the app with new or older preferences lacking `scan_subdirectories`. Confirm **Scan subdirectories** is off. Select Clips and use **Force Check Now**. Only loose.mp4 should upload and move to `Clips/Uploaded/loose.mp4`; nested, archive and junction entries must remain untouched.
3. Enable **Scan subdirectories**, restart the app, and confirm the toggle reloads as on. Start watching, then force another check after the active batch finishes. Nested clips should archive as `Uploaded/Game A/clip.mp4`, `Uploaded/Game B/clip.mp4`, and `Uploaded/Game A/deep/extra.mov`. Neither archive tree nor either junction should be visited.
4. Prepopulate an intended archive destination with different contents, then add a new clip of the same name to the matching source subdirectory. Force a check. Confirm the preexisting archive bytes remain unchanged and the new clip gets a suffixed archive name. Repeat rapidly to exercise collision suffixes.
5. After content was observed and moved, check the now-empty tree repeatedly. Expect one neutral empty notification and no repeated notifications. Add another distinct nested clip and confirm one later empty notification is re-armed. Keep the GUI responsive while changing folder selection and forcing checks.
6. Use **Upload File...** on a clip outside the watch root. Confirm its archive remains the sibling Uploaded directory. Toggle recursive scanning off, add a nested clip and a top-level clip, and confirm only the top-level clip is selected by periodic and manual checks.
7. In a separate test, make the archive destination unwritable or hold a source lock that prevents moving. After a successful test upload, confirm the original remains intact and the failure is logged; restore permissions and verify the file is not uploaded again automatically because its hash is in history. Inspect Uploaded for complete files only, with any interrupted staging artifacts hidden and excluded from scans.
