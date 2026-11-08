# Codex Start Here

This is the durable starting point for future implementation work. Follow [AGENTS.md](AGENTS.md) and [ARCHITECTURE.md](ARCHITECTURE.md). ChatGPT coordinates research/specification and independent GitHub review; Codex Desktop handles bounded local changes and verification. Do not merge or release without explicit user approval.

## Current development status

- P0 notification fix: merged in [PR #1](https://github.com/milan483/Youtube-Uploader/pull/1).
- P1A recursive scanning and archive: merged in [PR #2](https://github.com/milan483/Youtube-Uploader/pull/2).
- P1B Uploaded Clips Manager, P1C upload reliability, and P1D Linux desktop integration: consolidated and merged in [PR #6](https://github.com/milan483/Youtube-Uploader/pull/6).
- Windows and Linux release package workflow: merged in [PR #7](https://github.com/milan483/Youtube-Uploader/pull/7).

## Active implementation task

**P2 — Optional automatic deletion after successful uploads**

- Task specification: [.ai/tasks/p2-auto-delete-after-upload.md](.ai/tasks/p2-auto-delete-after-upload.md).
- Work branch: `feat/auto-delete-after-upload`.
- Keep `delete_after_upload` disabled by default.
- When enabled, send a confirmed uploaded local file to OS Trash/Recycle Bin instead of moving it into `Uploaded/`.
- Preserve current archive behavior when disabled. Never permanently delete files or delete remote YouTube videos.
- The task specification defines the lifecycle, safety checks, tests, and acceptance criteria.

Read the task specification and relevant sections of [ARCHITECTURE.md](ARCHITECTURE.md) before editing. Preserve local changes, run focused and full tests, update the task document with exact evidence, and report implementation/validation on the draft PR.

## Workflow

For later tasks, create a bounded specification under `.ai/tasks/`, update this entry point, and use one dedicated branch and draft PR. GitHub Issues are disabled in this repository, so the task branch and draft PR are the coordination record. Never assume roadmap entries authorize work.

Never merge pull requests or publish releases without explicit user approval.
