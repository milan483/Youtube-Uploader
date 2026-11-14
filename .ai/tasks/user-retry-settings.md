# User retry settings for 0.2.2

## Scope

User approved retry limit and retry delays. Work on `feat/user-retry-settings`
from main `79e6032`. Keep unrelated behavior and existing preferences intact.

- Add a Retry Settings dialog with total attempts (1 to 100), initial retry delay
  (1 to 86400 seconds), and maximum retry delay (1 to 86400 seconds).
- Require maximum delay to be at least initial delay. Defaults remain 3, 60,
  and 3600. Save together; Cancel has no effect; show persistence errors.
- Persist through StateManager. Invalid new values use safe defaults without
  discarding unrelated existing preferences.
- Use saved settings consistently for upload scheduling, retry eligibility,
  and batch exhaustion classification. Snapshot settings per upload attempt.
- Existing retry deadlines remain intact. Increasing the limit can make
  exhausted files eligible. Internal transient transport retries stay unchanged.
- Set application version to 0.2.2. No release publication is authorized.

## Acceptance evidence

Focused tests cover defaults, persistence, bad input, retry eligibility,
batch classification, capped backoff, and settings dialog save behavior.
Run the full test suite, compile checks, and available desktop smoke checks.
Report local results separately from CI and live YouTube behavior.

## Status

Implemented on `feat/user-retry-settings` for version 0.2.2.

Changed: GUI button and `retry_settings_dialog.py`; shared validation in
`utils/retry_settings.py`; StateManager and PreferencesStore persistence;
UploadManager scheduling; BatchUploader eligibility snapshot; version,
README, architecture contract, and focused regression tests.

Local validation on 2026-11-14:

- Baseline: `python -m pytest -q`, 115 passed on Python 3.13.
- Focused first pass: retry utility/dialog/state/upload/batch tests, 82 passed.
- Final `python -m pytest -q`: 148 passed on Python 3.13.16 (2.85s),
  and 148 passed on Python 3.11.17 (2.96s).
- `python -m compileall -q .`, `python main.pyw --smoke-test`, and
  `git diff --check`: passed.
- Real Tk dialog with isolated temporary preferences: Cancel, save/reload,
  Restore Defaults without immediate saving, bad-input rejection, and a
  simulated disk failure all passed. Screenshot inspected for clipping.
- Tests verify bounded settings, safe legacy defaults, unrelated preference
  preservation, limits of 1 and 100, capped delays, per-upload and batch
  policy snapshots, unchanged deadlines, and exhausted-file eligibility.

Evidence and isolated Python environments are under
`/home/kylan/.codex/outputs/youtube-uploader-retry-settings-20261114/`.
Windows desktop interaction and live YouTube uploads have not been run.
Implementation commit: `0baee54680a1eee5f48f0837ab94f88ca7de7ebe`.
Draft PR: [#9](https://github.com/milan483/Youtube-Uploader/pull/9).
Windows/Linux tests and package builds run on the PR; see its check results
for CI evidence, separate from the local validation above.
No release has been published.
