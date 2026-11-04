# Codex Start Here

This is the entry point for implementation work in this repository.

## Workflow

- ChatGPT owns repository inspection, architectural research, task specifications, and independent PR review.
- Codex Desktop owns bounded implementation and local tests.
- GitHub is the durable record for plans, commits, verification, PR reports, and review feedback.

Avoid repeating discovery already recorded in the active task. Inspect additional code or conduct outside research only when it is required to implement or verify a specific unresolved detail.

## Read first

1. [AGENTS.md](AGENTS.md) for repository-wide constraints.
2. [ARCHITECTURE.md](ARCHITECTURE.md) for module boundaries and callback contracts.
3. The active task specification below.

## Active task: P1A — recursive scanning and centralized archive

- **Task:** [.ai/tasks/p1a-recursive-scan-and-archive.md](.ai/tasks/p1a-recursive-scan-and-archive.md)
- **Status:** Implemented and locally validated; awaiting independent review on draft PR #2.
- **Working branch:** feat/p1-recursive-archive
- **Base branch:** main
- **Draft PR:** https://github.com/milan483/Youtube-Uploader/pull/2
- **Scope:** Optional recursive watch-folder scanning and safe preservation of source subdirectory structure beneath a central Uploaded archive. Nothing else.

P0 notification deduplication was merged in PR #1 and should be preserved. The follow-on P1B task, [.ai/tasks/p1b-uploaded-clips-manager.md](.ai/tasks/p1b-uploaded-clips-manager.md), is **queued**, not yet authorized for implementation. Likewise, upload-reliability and Linux integration work remain in the roadmap.

## Codex checklist

1. Confirm the remote branch and existing draft PR; check the local working tree and preserve existing changes. Do not create a duplicate PR.
2. Read the active P1A task and inspect the named call sites. Make only the necessary scoped edits.
3. Implement and extend deterministic file-discovery, archive-path, preferences, batch/orchestrator, and upload regression tests. Do not require live YouTube API access.
4. Run focused tests, followed by the full suite:
   - python -m pytest tests/test_file_handler.py tests/test_batch_uploader.py tests/test_upload_manager.py tests/test_watch_controller.py -q
   - python -m pytest -q
5. Record implementation results, actual commands, counts, changed files, and limitations in the task file and existing draft PR.
6. Commit and push to feat/p1-recursive-archive. Keep PR #2 in draft for independent review.
7. Do not merge or publish anything without the user's explicit approval.

Use task-specific brief handoffs instead of generating large prompts. New workstreams require new task specs and an updated pointer in this file. Do not implement queued phases simply because they are listed in a roadmap.
