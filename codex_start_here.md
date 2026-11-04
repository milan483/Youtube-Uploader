# Codex Start Here

This file is the entry point for implementation work in this repository. Read it before starting a task.

## Working model

- ChatGPT coordinates research, repository analysis, design decisions, task specifications, and independent PR review.
- Codex Desktop implements the assigned scope, runs local verification, and reports results.
- GitHub is the durable source of truth for task specifications, implementation reports, commits, and review findings.

Reuse the research and decisions already recorded here. Do not repeat broad repository exploration or external research unless implementation reveals a specific unresolved question.

## Read these files

1. AGENTS.md — persistent repository instructions.
2. ARCHITECTURE.md — module boundaries, callback contracts, and runtime flow.
3. The active task specification below.

## Active task

**P0: Prevent repeated empty watch-folder notifications**

- Specification: [.ai/tasks/p0-empty-folder-notification.md](.ai/tasks/p0-empty-folder-notification.md)
- Status: Ready for implementation
- Task branch: fix/p0-empty-folder-notification
- Target branch: main
- Scope: notification deduplication and its focused regression tests only.

The branch containing this handoff documentation is intended to be the working branch for this task. If you are continuing the task, verify the current branch and remote state before editing. Do not create a duplicate branch or PR if one already exists.

## Implementation procedure

1. Inspect git status --short, the current branch, and its upstream. Preserve all pre-existing local changes.
2. Read the active task specification and inspect only the relevant implementation and tests.
3. Implement only the specified scope. Do not begin future roadmap items.
4. Add or update focused regression tests.
5. Run the focused test module, then the complete test suite:
   - python -m pytest tests/test_watch_controller.py -q
   - python -m pytest -q
6. Update the task specification with the result, changed files, commands, and test outcomes.
7. Commit and push to the assigned branch. Create or update one draft PR against main; check for an existing PR first.
8. Put a concise implementation report in the PR, including the commit SHA, test results, and any remaining limitations.

Do not merge the PR. ChatGPT will independently review the latest diff, task specification, report, and CI results.

## Future tasks

For each substantial new task:

- Create a separate, bounded specification in .ai/tasks/<slug>.md.
- Update this file so the active task points to the correct specification and branch.
- Add or update .ai/plans/ only for durable multi-phase plans.
- Avoid duplicating project-wide rules from AGENTS.md or architecture details from ARCHITECTURE.md.
- Keep the handoff concise enough that Codex can start without rediscovering decisions already made.
