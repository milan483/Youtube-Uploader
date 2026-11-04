# Implementation Roadmap

This is a planning document, not authorization to implement every item. Each item should receive its own bounded task specification before Codex starts work.

## P0 — Notification correctness

- [ ] Deduplicate empty watch-folder notifications.
- [ ] Avoid an empty notification on initial startup when the selected folder has no supported videos.
- [ ] Use accurate notification wording; an empty supported-video scan does not prove every file was uploaded successfully.

Active specification: [P0 empty-folder notification](../tasks/p0-empty-folder-notification.md).

## P1 — Recursive scanning and archive management

- [ ] Add configurable recursive scanning of nested directories. Preserve current behavior by default for existing installations unless the migration/default policy is explicitly decided.
- [ ] Exclude the managed Uploaded archive from scanning to prevent re-upload loops.
- [ ] Centralize successfully uploaded clips in one Uploaded archive while preserving each source file's relative directory structure.
- [ ] Prevent filename collisions and avoid following directory symlinks or paths outside the selected watch root.
- [ ] Add an Uploaded Clips Manager to browse archived files, show useful metadata/total size, and select individual or multiple clips for deletion.
- [ ] Prefer moving deleted clips to the operating system Trash/Recycle Bin. Require confirmation for bulk deletion and constrain deletion to the managed archive.
- [ ] Keep local clip deletion independent from the corresponding YouTube video.

## P1 — Upload reliability

- [ ] Classify relevant SSL/TLS EOF and connection-reset failures as transient network errors.
- [ ] Recover interrupted resumable uploads using the existing upload session and confirmed server offset where supported, rather than blindly restarting the entire transfer.
- [ ] Preserve retry counts and upload state across retries and application restarts.
- [ ] Prevent concurrent duplicate uploads of the same file and verify completion before starting another upload attempt.
- [ ] Add deterministic tests for interruption, recovery, duplicate prevention, and retry exhaustion.

## P1 — Linux desktop support

- [ ] Separate core dependencies from Windows-only dependencies.
- [ ] Implement native Linux desktop notifications.
- [ ] Verify system tray behavior and safe fallback under KDE Plasma Wayland; never hide the main window if a usable tray entry was not created.
- [ ] Use appropriate XDG configuration, data, and state directories for persistent files.
- [ ] Apply restrictive POSIX permissions to OAuth token material and review token serialization.
- [ ] Add Linux installation documentation and CI coverage. Treat KDE Plasma Wayland as an explicit test target while preserving Windows functionality.

## Delivery and review

For each item or coherent group of items:

1. Research and resolve design choices in ChatGPT.
2. Create a bounded task file under .ai/tasks/.
3. Update codex_start_here.md to point to the active task.
4. Implement and verify on a dedicated branch.
5. Publish a draft PR with changed files, test commands/results, and limitations.
6. Have ChatGPT independently review the latest diff and CI.
7. Merge only after the user's explicit approval.
