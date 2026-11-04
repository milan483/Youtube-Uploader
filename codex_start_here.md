# Codex Start Here

ChatGPT coordinates research/specification and independent PR review; Codex handles bounded implementation and validation. GitHub is the source of truth. Read [AGENTS.md](AGENTS.md) and [ARCHITECTURE.md](ARCHITECTURE.md) first.

## Status

- P0 and P1A: merged in PR #1 and PR #2.
- P1B Uploaded Clips Manager: separate [PR #3](https://github.com/milan483/Youtube-Uploader/pull/3), still in review.
- **P1C upload reliability**: code and regression tests prepared on `fix/p1c-upload-reliability` (this branch); validation/CI and review pending.
- P1D Linux support: separate workstream in the roadmap.

## P1C task

Read [.ai/tasks/p1c-upload-reliability.md](.ai/tasks/p1c-upload-reliability.md). Continue the existing P1C branch and PR, preserve local changes, run the focused and full pytest suites and inspect Windows/Linux CI results. Post actual test results and caveats to the PR. Do not merge or expand into P1B/P1D without specific authorization.
