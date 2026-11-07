# P1B — Uploaded Clips Manager and safe local cleanup

- **Status:** Implemented in GitHub; awaiting tests, CI and Windows smoke verification.
- **Repository:** milan483/Youtube-Uploader
- **Branch:** feat/p1b-uploaded-clips-manager
- **Base:** main (PR #2 already merged)
- **Scope:** Only manual cleanup of archived local files. Never delete YouTube videos.

## Implementation

- `services/uploaded_clips_manager.py`: filesystem-only browsing and Trash operations. Uses the selected watch root's central `Uploaded` folder, recursive relative paths, file sizes, per-file errors, strict path containment, rejection of junctions/symlinks and incomplete/hidden files.
- `uploaded_clips_dialog.py`: Tkinter management dialog listing archived clips, disk usage, Refresh, Select All, Delete Selected, Delete All and Close. Sends operations to background threads and updates UI on the Tk main loop. Always confirms deletion, naming the fixed snapshot of the archive root.
- `gui.py`: adds the Uploaded Clips button and launches the dialog for the current watch root.
- `file_handler.py`: same-process `archive_lock` serializes archive moves with manager reads and deletes, preventing in-progress archive publication from being selected.
- `requirements.txt`: adds the cross-platform `send2trash` dependency. When missing, the manager fails closed and does not fall back to permanent deletion.
- `tests/test_uploaded_clips_manager.py`: deterministic enumeration, scoped deletion, partial failure, traversal/symlink and stale-selection tests.
- `.github/workflows/python-tests.yml`: pytest workflow for Python 3.11/3.13 on Ubuntu and Windows.

## Acceptance criteria

- Archived clips from nested game folders are listed with correct relative paths, sizes and total.
- Only videos under the central archive are selectable; hidden staging, symlinks, junctions and non-video files are excluded.
- Delete Selected and Delete All ask for confirmation and send only chosen clips to OS Trash; bulk operations report individual failures and refresh.
- A missing Trash provider or permission error never silently leads to permanent deletion.
- Deleting local copies never modifies upload history, retry state or any remote YouTube video.
- Changing the main window's watch root cannot silently retarget an already-open dialog.
- Concurrent in-process archiving is serialized by the file-handler lock.
- Existing recursive scanning, P0 notifications and manual single-file upload behavior are unchanged.

## Validation

Run `python -m pytest tests/test_uploaded_clips_manager.py tests/test_file_handler.py -q` and `python -m pytest -q`. Inspect GitHub Actions for both Windows and Linux. This handoff was authored through GitHub with no local repository checkout; **do not claim tests have passed until evidence is available**.

### Manual Windows smoke check

1. In a disposable watch folder, create `Uploaded/Game A/clip.mp4`, `Uploaded/Game B/clip.mp4` and a fake hidden `.upload-staging-123.part` file.
2. Open Uploaded Clips. Verify paths, sizes and count and ensure the hidden artifact isn't shown.
3. Select only one clip and Delete Selected; cancel once, then confirm. Verify that only that clip is in Recycle Bin.
4. Delete All and verify the other clip moves to Recycle Bin, not permanently removed, and YouTube/history are unchanged.
5. Change the main window's watch folder with a dialog still open. Verify the dialog clearly displays and continues to use its original root.
6. Test missing Trash dependency and locked file failures; ensure no permanent deletion and useful error messages.

## Known limits

Protection from malicious concurrent changes by *other processes* is best-effort, not transactional. Old nested Uploaded directories are not migrated or managed. Windows Explorer may limit Trash support for some network shares; failures are surfaced.

## Completion record

- **Verification pending**: command outputs, commit SHA, PR URL, and smoke results to be updated after review.
