# P1B–P1D Consolidated Integration

- **Status:** All implementations committed; independent review / desktop smoke / merge pending
- **Branch:** integration/p1-all
- **Base:** main (P0 and P1A already merged)
- **Purpose:** One conflict-free final integration path combining separately tested P1B, P1C and P1D. Do not merge the individual draft PRs #3, #4 or #5 separately once this consolidated PR is accepted.

## Included deliverables

- P1B: [.ai/tasks/p1b-uploaded-clips-manager.md](p1b-uploaded-clips-manager.md). Tkinter archive browser, safe local Trash and mutual exclusion with archive moves.
- P1C: [.ai/tasks/p1c-upload-reliability.md](p1c-upload-reliability.md). SSL EOF transient classification, same-request resumable retries, retry-count preservation and in-process upload serialization.
- P1D: [.ai/tasks/p1d-linux-desktop.md](p1d-linux-desktop.md). Linux XDG directories, optional Wayland tray indicator, safe taskbar fallback, notify-send notifications, XDG autostart, POSIX token permissions and conditional dependencies.

## Test evidence

Windows and Linux matrix: Python 3.11 and 3.13 on GitHub Actions. All four isolated PR jobs passed for each of #3, #4 and #5. The combined branch also passed all four integration jobs before the final documentation update. Recheck the current final commit's CI result.

Focused regression tests are included in `tests/test_uploaded_clips_manager.py`, `tests/test_upload_manager.py`, `tests/test_state_manager.py`, `tests/test_linux_desktop.py` and existing file-handling tests. The Python suite uses fakes and does not contact YouTube.

## Remaining manual smoke

1. Windows: launch the app, open Uploaded Clips, cancel/confirm single and bulk Trash, recover a file from Recycle Bin, confirm upload history and remote YouTube unchanged.
2. Upload reliability: interrupt a disposable test account's upload after meaningful progress; confirm the client resumes its session where the API allows and doesn't duplicate the video.
3. Linux KDE Plasma Wayland: start from a non-repository working directory, verify app token/state files under XDG, test notify-send and indicator Show/Exit, confirm taskbar fallback if no tray; test XDG autostart.
4. Validate a real Windows file collision, junction exclusion and locked-source failure (P1A/P1B interaction).

## Known limits

No interactive Windows/Plasma session or live YouTube credentials are accessible in GitHub CI. Same-process locking does not prevent separate application instances from racing. Pickle token storage remains trusted-local-file-only. Symlink and path checks cannot guarantee safety against malicious concurrent filesystem replacement by another process.

## Integration record

- **Final commit:** record in consolidated PR.
- **GitHub Actions:** inspect the consolidated PR check rollup.
- **Manual smoke:** pending.
- **Merge:** pending explicit user approval.
