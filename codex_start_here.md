# Codex Start Here

This is the durable starting point for future implementation work. Follow [AGENTS.md](AGENTS.md) and [ARCHITECTURE.md](ARCHITECTURE.md). ChatGPT coordinates research/specification and independent GitHub review; Codex Desktop handles bounded local changes and verification. Do not merge or release without explicit user approval.

## Current development status

- P0 notification fix: merged in [PR #1](https://github.com/milan483/Youtube-Uploader/pull/1).
- P1A recursive scanning and archive: merged in [PR #2](https://github.com/milan483/Youtube-Uploader/pull/2).
- P1B, P1C and P1D: **implemented together** on `integration/p1-all` for final integration review. See [.ai/tasks/p1-complete-integration.md](.ai/tasks/p1-complete-integration.md).
- The individual P1B/P1C/P1D branches and PRs #3–5 were used for isolated changes and CI; the combined PR supersedes them to avoid merge conflicts.

## Next steps

No new implementation task is active. Review the consolidated PR, check the GitHub Actions Windows/Linux matrix, and complete the real Windows Recycle Bin, live YouTube resumable upload, and KDE Plasma Wayland smoke checks if possible.

For later tasks, create a bounded task specification under `.ai/tasks/`, update this entry point to it, and use one dedicated branch and draft PR. Never assume roadmap entries automatically authorize work.
