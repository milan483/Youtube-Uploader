# Implementation Roadmap

## Completed implementations

- [x] **P0** empty notification fix — merged [PR #1](https://github.com/milan483/Youtube-Uploader/pull/1).
- [x] **P1A** recursive scanning and central archive — merged [PR #2](https://github.com/milan483/Youtube-Uploader/pull/2).
- [x] **P1B** Uploaded Clips Manager and safe OS Trash backend — implemented, CI passed in PR #3.
- [x] **P1C** resumable SSL EOF recovery and preserved retry counts — implemented, CI passed in PR #4.
- [x] **P1D** XDG paths, Linux notifications, Wayland AppIndicator/tray fallback, autostart and token modes — implemented, CI passed in PR #5.

All three remaining workstreams are also combined in `integration/p1-all` for a single review/merge path. Documentation and automated tests do not substitute for desktop or live-network smoke testing.

## Pending gates

- [ ] Consolidated final PR independently reviewed.
- [ ] Windows Recycle Bin and file-lock/collision smoke check.
- [ ] Live resumable YouTube test after a transient disconnect.
- [ ] KDE Plasma Wayland system-tray, notifications, autostart and OAuth smoke.
- [ ] Explicit user approval for merge; no releases without separate approval.

No new features are authorized solely by this roadmap.
