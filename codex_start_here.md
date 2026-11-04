# Codex Start Here

GitHub contains the durable task history. ChatGPT handles repository analysis and independent PR review. Codex Desktop handles bounded local implementation and verification. Do not duplicate PRs or merge without explicit user approval.

## Status
- P0 merged: PR #1.
- P1A merged: PR #2.
- P1B Uploaded Clips Manager: [PR #3](https://github.com/milan483/Youtube-Uploader/pull/3).
- P1C Upload reliability: [PR #4](https://github.com/milan483/Youtube-Uploader/pull/4).
- **P1D Linux desktop support:** code and tests prepared on `feat/p1d-linux-desktop` in this branch; CI and KDE Wayland smoke test pending.

Read [AGENTS.md](AGENTS.md), [ARCHITECTURE.md](ARCHITECTURE.md) and [.ai/tasks/p1d-linux-desktop.md](.ai/tasks/p1d-linux-desktop.md).

## P1D verification follow-up
Check the existing draft P1D PR, preserve local changes and do not start a new branch. Run `python -m pytest tests/test_linux_desktop.py -q` and `python -m pytest -q`. Inspect all Windows/Linux CI jobs and test actual KDE Plasma Wayland notification/tray/autostart behavior. Publish evidence and fixes on the existing PR. Do not touch P1B/P1C except for required merge-conflict integration after approved merges.
