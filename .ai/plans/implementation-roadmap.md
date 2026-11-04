# Implementation Roadmap

This is a planning document. A roadmap checkbox is not authorization to implement a phase; Codex acts only on the active task linked from `codex_start_here.md`.

## P0 — Notification correctness (merged)

- [x] Deduplicate empty watch-folder notifications.
- [x] Do not alert on initially empty folders.
- [x] Use neutral wording when no supported videos were found.

Completed in [PR #1](https://github.com/milan483/Youtube-Uploader/pull/1).

## P1A — Recursive scanning and central archive (active)

Detailed spec: [.ai/tasks/p1a-recursive-scan-and-archive.md](../tasks/p1a-recursive-scan-and-archive.md).

- [ ] Optional recursive scan (default off for backward compatibility).
- [ ] Exclude root and nested Uploaded archives, outside-root symlinks, and unsafe paths.
- [ ] Centralize successful watch-mode archives beneath `<watch_root>/Uploaded/`, preserving relative subdirectories.
- [ ] Ensure file collisions and failures never overwrite/delete originals.
- [ ] Preserve existing watch/retry/manual-upload behavior and add focused tests.

## P1B — Uploaded Clips Manager (queued after P1A review)

Preliminary spec: [.ai/tasks/p1b-uploaded-clips-manager.md](../tasks/p1b-uploaded-clips-manager.md).

- [ ] Browse/archive size and multi-select in a management dialog.
- [ ] Manually send selected local archived clips to Trash/Recycle Bin with confirmation.
- [ ] Prevent deletion outside the managed archive or of in-progress clips.
- [ ] Preserve upload history and remote YouTube content.
- [ ] Add deterministic safety tests and Windows UI smoke verification.

## P1C — Upload reliability (not started)

- [ ] Recognize SSL/TLS EOF and relevant connection-reset failures as transient errors.
- [ ] Recover resumable upload sessions and offsets where supported.
- [ ] Preserve retry counters and prevent concurrent duplicate uploads.
- [ ] Add interruption, retry-exhaustion, and deduplication regression tests.

## P1D — Linux desktop support (not started)

- [ ] Separate cross-platform versus Windows-only dependencies.
- [ ] Implement Linux desktop notifications.
- [ ] Verify safe tray behavior/fallback on KDE Plasma Wayland.
- [ ] Use XDG directories and restrictive POSIX token permissions.
- [ ] Add Linux installation docs, CI, and platform-level smoke coverage.

## Delivery requirements

For each new phase: ChatGPT inspects current code and records the bounded task → Codex implements/tests on a dedicated branch and updates one draft PR → ChatGPT reviews its latest diff, report, and available CI → user explicitly approves merges. Do not duplicate open tasks/PRs.
