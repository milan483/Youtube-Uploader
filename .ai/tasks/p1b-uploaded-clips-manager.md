# P1B — Uploaded Clips Manager and safe local deletion

- **Status:** Queued; DO NOT implement as part of P1A
- **Dependency:** P1A recursive scanning and centralized archive, after review
- **Branch/PR:** Not yet assigned; create a dedicated task branch and draft PR after P1A
- **Implementer:** Codex Desktop
- **Reviewer:** ChatGPT through GitHub

## Objective

Add a small Windows-compatible Tkinter interface for viewing and cleaning up the local files in the current watch root's `Uploaded` archive. Deleting a local clip **must not** delete the YouTube upload or erase upload-history metadata.

## Planned behavior

1. Add an **Uploaded Clips** control to the main GUI; it opens a management dialog for the **current watch root's** `Uploaded` directory.
2. List files recursively within that archive, with root-relative names, sizes, and a total storage figure. Support Refresh, Select All, Select Individual, Delete Selected, and Delete All.
3. Deletion is **manual only**, to the operating system's Trash/Recycle Bin using an appropriate cross-platform backend such as `send2trash`, not permanent `os.remove`. Ask for confirmation showing file count and total size for bulk deletion.
4. Fail closed when system Trash is unavailable; never silently fall back to permanent deletion. Show partial successes and per-file failures, then refresh the list.
5. Constrain all deletions to the canonical managed archive root. Reject symlinks and path traversal, revalidate after selection and immediately before deletion, and do not follow symlink directories.
6. Never permit deletion of source files outside the managed archive, including files in the active watch directory or other paths that merely share a textual prefix.
7. Avoid deleting files still being archived/copied or otherwise in use; coordinate with P1A's complete-file staging/finalization. Do not expose staging files as selectable clips.
8. Do not modify `upload_history.json`, remote YouTube content, or upload-state records when archiving copies are deleted. The duplicate-detection history should continue preventing duplicate uploads of identical content.
9. Keep the UI responsive during filesystem enumeration and Trash operations; marshal widget updates to Tk's main thread.
10. Keep archived files from older, per-subfolder Uploaded directories **out of the new manager** initially; do not migrate or delete those automatically. Document the limitation.

## Acceptance and tests

- Correct recursive listing, sizes, total storage, empty-archive state, and path display for duplicate filenames in different subdirectories.
- Delete one, selected multiple, or all, with correct confirmation and refreshed data.
- Mock Trash operations to prove only selected files under the managed root are targeted.
- Validate symlink, traversal, changing-root, missing-file, permission-denied, partly failed Trash, and in-progress archive protections.
- Prove deletion leaves local upload history and remote YouTube videos untouched.
- Verify the manager is usable under Windows; require a manual GUI smoke checklist in addition to deterministic unit tests.

## Handoff after P1A

Before implementation, ChatGPT should update this specification with the final P1A archive API and path conventions, set an independent branch and PR, and point `codex_start_here.md` to this task. Do not implement P1B solely from this queued plan.
