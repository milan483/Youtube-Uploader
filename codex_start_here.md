# Codex Start Here

## Workflow
ChatGPT coordinates repository analysis, plans and PR review; Codex Desktop implements and validates bounded tasks; GitHub records the work. Preserve local changes, don't duplicate branches/PRs and don't merge without user approval.

Read [AGENTS.md](AGENTS.md), [ARCHITECTURE.md](ARCHITECTURE.md), and the active task.

## Current status

- P0 merged: [PR #1](https://github.com/milan483/Youtube-Uploader/pull/1).
- P1A merged: [PR #2](https://github.com/milan483/Youtube-Uploader/pull/2).
- **P1B** Uploaded Clips Manager has been implemented in branch `feat/p1b-uploaded-clips-manager` as a ChatGPT-authored change, pending test/CI results and independent review.
- P1C upload reliability and P1D Linux support are separate workstreams tracked in [.ai/plans/implementation-roadmap.md](.ai/plans/implementation-roadmap.md).

## P1B continuation if requested

Read [.ai/tasks/p1b-uploaded-clips-manager.md](.ai/tasks/p1b-uploaded-clips-manager.md). Use the existing P1B branch and PR, do not duplicate either. Run `python -m pytest tests/test_uploaded_clips_manager.py tests/test_file_handler.py -q` followed by `python -m pytest -q` on Windows and Linux. Review CI results; smoke-test the dialog with a disposable archive. Post concrete test results and any defects to the PR. Avoid P1C/P1D changes unless separately assigned.

After P1B review, update this entry point to the next active task. Never assume a roadmap entry is authorization to implement it.
