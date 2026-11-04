# Repository Instructions

These instructions apply to all work in this repository.

## Read before making changes

1. Read codex_start_here.md for the active handoff and workflow.
2. Read ARCHITECTURE.md before changing cross-module behavior or internal contracts.
3. Read the task specification under .ai/tasks/ for the assigned scope.

Do not reread or explore unrelated parts of the repository when the task specification and current context already identify the relevant code.

## Project conventions

- This is a Python desktop application using Tkinter, with separate controller, service, authentication, storage, and platform-integration modules.
- Preserve the existing layered architecture. Keep UI concerns in gui.py, folder orchestration in controllers/, batch sequencing in services/, upload behavior in upload_manager.py, and persistence behind storage/ and state_manager.py.
- Treat callback names/signatures and the contracts documented in ARCHITECTURE.md as internal APIs. Update all producers, consumers, tests, and documentation together if a contract must change.
- Follow the surrounding code style and keep changes narrowly scoped. Avoid new dependencies unless they are necessary and justified.
- Preserve existing Windows behavior. For cross-platform work, isolate OS-specific integrations and test the target platform rather than assuming compatibility.
- Unit tests should remain independent of live YouTube API calls and external network access. Use fakes or mocks.
- Do not log OAuth tokens, secrets, or other credentials. Never commit client_secrets.json, token.pickle, or local runtime state.

## Implementation workflow

- Before editing, inspect git status --short and git branch --show-current. Preserve pre-existing local changes; do not overwrite or discard user work.
- Work only on the task assigned in codex_start_here.md or the explicitly referenced task specification. Do not expand scope without approval.
- Make focused changes and add regression tests for changed behavior.
- Run the most relevant focused tests first, then run the full suite with python -m pytest -q.
- Update ARCHITECTURE.md, README.md, or task documentation only when the implementation changes documented behavior or contracts.
- Update the task specification with its implementation status, changed files, test commands/results, and commit/PR references.
- Commit and push to the assigned task branch, then create or update a draft PR against main. Do not commit directly to main.
- Include a concise implementation and verification report in the PR description or a PR comment.
- Never merge a PR, publish a release, or perform other consequential repository actions without explicit user approval.

## Handoff documentation

- codex_start_here.md is the primary entry point for Codex.
- Detailed, bounded tasks belong in .ai/tasks/<task-name>.md.
- Durable multi-phase plans belong in .ai/plans/ when they provide value.
- Keep these files concise, avoid duplicating the same instructions, and update existing documents rather than creating competing copies.
