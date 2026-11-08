# P2 — Optional automatic deletion after successful uploads

- **Status:** Specification ready; implementation pending.
- **Repository:** `milan483/Youtube-Uploader`
- **Branch:** `feat/auto-delete-after-upload`
- **Base:** `main`
- **Scope:** Opt-in cleanup of the local source video after a confirmed YouTube upload. Never delete the remote YouTube video.

## User-facing behavior

Add an Automation Settings checkbox:

**Delete local videos after successful upload (move to Trash)**

- Persist it as `delete_after_upload`.
- Default to `false`, including for existing preference files where the key is absent.
- When disabled, preserve the existing behavior: move successfully uploaded local files into the `Uploaded/` archive.
- When enabled, send the uploaded local source file to the operating system's Trash/Recycle Bin instead of archiving it.
- Apply the setting to both watched-folder uploads and manual **Upload File...** uploads.
- Do not automatically delete older files already in `Uploaded/`; the existing Uploaded Clips Manager remains responsible for manual archive cleanup.

## Existing implementation context

- `upload_manager.py`: `UploadManager._upload_video_locked()` owns upload, playlist insertion, archive move, upload-history persistence, and completed state.
- `file_handler.py`: owns safe file operations and the shared `archive_lock`.
- `services/uploaded_clips_manager.py`: already uses the cross-platform `send2trash` package and fails closed; reuse its safety principles rather than introducing permanent deletion.
- `state_manager.py`: owns preference defaults and persistence.
- `storage/preferences_store.py`: validates preference schema.
- `gui.py`: builds Automation Settings, restores preferences, and saves checkbox changes.
- `ARCHITECTURE.md`: documents the upload lifecycle and module contracts.

## Safety and lifecycle requirements

1. Add `DEFAULT_DELETE_AFTER_UPLOAD = False` and a boolean `delete_after_upload` preference. Validate the type and ensure old settings files default to false.
2. Only attempt local cleanup after the YouTube upload request returns a non-empty video ID and `add_upload_to_history(...)` completes successfully.
3. The current contract treats playlist insertion failure as a warning after a successful video upload. Preserve this behavior; a playlist warning alone must not reclassify the video upload as failed or trigger a retry.
4. Before moving a file to Trash:
   - For watched-folder uploads, re-run the existing watch-root containment and symlink/junction checks.
   - For manual uploads, verify the selected path still points to a regular, non-symlink/non-junction file.
   - Recompute the file hash and compare it with the hash calculated before upload. If the file has changed, leave it in place and report a cleanup warning.
5. Use the existing `send2trash` dependency / OS Trash integration. Never use `os.remove`, `unlink`, recursive deletion, or another permanent-delete fallback.
6. Serialize the file operation with `FileHandler.archive_lock` where appropriate.
7. If the dependency is missing, Trash is unavailable, the path is unsafe, the file changed, or the Trash operation fails:
   - leave the local file untouched;
   - log and surface a clear cleanup warning;
   - keep the YouTube upload recorded as successful;
   - persist completed/uploaded state so the app does not retry or re-upload the same video.
8. Do not change existing archive behavior when the preference is false. Preserve nested relative paths, no-overwrite collision behavior, and the Uploaded Clips Manager.
9. Do not delete YouTube videos or alter upload-history entries during local cleanup.

## Acceptance criteria

- [ ] New and legacy preferences default to `delete_after_upload = false`.
- [ ] Non-boolean values are rejected by preference schema validation.
- [ ] The checkbox loads and saves the preference on Windows and Linux.
- [ ] Enabled + confirmed watched-folder upload: source is sent to OS Trash; no new `Uploaded/` copy is created.
- [ ] Enabled + confirmed manual upload: selected source is sent to OS Trash.
- [ ] Disabled: existing move-to-`Uploaded/` behavior is unchanged.
- [ ] Failed, interrupted, quota-exceeded, duplicate-skipped, or unconfirmed uploads never trigger cleanup.
- [ ] Playlist insertion warnings do not turn a confirmed video upload into a failure; preserve the current outcome contract.
- [ ] A source file changed during upload is preserved and produces a cleanup warning.
- [ ] Unsafe paths, symlinks, junctions, and non-regular files are never sent to Trash.
- [ ] Trash/dependency failures preserve the file and do not cause a successful upload to become retryable.
- [ ] Upload history and completed state remain correct whether cleanup succeeds or fails.
- [ ] Existing Uploaded Clips Manager behavior and tests remain unchanged.
- [ ] README and ARCHITECTURE.md explain the option, default-off behavior, Trash semantics, and failure handling.

## Validation

- Add deterministic unit tests with an injected/fake Trash function. Tests must not touch a real OS Trash or live YouTube API.
- Cover watch and manual uploads, default-off and enabled paths, upload failures, duplicates, quota errors, playlist warnings, changed source content, unsafe paths, and Trash failures.
- Run focused upload, file-handler, preference/state, and Uploaded Clips Manager tests.
- Run the full suite: `python -m pytest -q`.
- Verify the existing Windows/Linux GitHub Actions matrix.
- Include exact test commands/results in the PR report.
- Complete manual smoke tests on Windows Recycle Bin and Linux desktop Trash before calling platform behavior fully verified.

## Handoff

Read `AGENTS.md`, `codex_start_here.md`, `ARCHITECTURE.md`, and this task specification before editing. Preserve local changes. Keep implementation limited to this task, update this document with evidence, and do not merge or publish a release.