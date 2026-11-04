# Implementation Roadmap

This is a tracking document, not authorization to merge or release. Each P1 workstream should remain independently reviewable.

- [x] **P0 notifications** — merged [PR #1](https://github.com/milan483/Youtube-Uploader/pull/1).
- [x] **P1A recursive scanning / central archive** — merged [PR #2](https://github.com/milan483/Youtube-Uploader/pull/2).
- [ ] **P1B local Uploaded Clips Manager and safe Trash** — implementation prepared on `feat/p1b-uploaded-clips-manager`; tests/smoke/merge pending. See [.ai/tasks/p1b-uploaded-clips-manager.md](../tasks/p1b-uploaded-clips-manager.md).
- [ ] **P1C upload reliability** — SSL EOF classification, resumable upload continuation, retry-state persistence, quota/duplicate safety, deterministic tests.
- [ ] **P1D Linux support** — platform-conditional dependencies, native notifications, reliable tray/fallback under KDE Plasma Wayland, Linux autostart and configuration directories, POSIX credential permissions, Linux CI/tests.

For each task: focused branch and draft PR, implementation report with test evidence, independent review, and explicit user approval for merge.
