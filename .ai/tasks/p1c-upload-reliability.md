# P1C — Upload reliability, resumable retries and retry-state preservation

- **Status:** Implemented in GitHub; awaiting CI and independent review
- **Branch:** fix/p1c-upload-reliability
- **Base:** main (P1A merged)
- **Focus:** SSL EOF recovery, resumable continuation, durable retry metadata, in-process duplicate avoidance.

## Existing root causes

- `UploadManager._is_transient_network_error()` omitted `ssl.SSLEOFError` and EOF protocol errors.
- `UploadManager.upload_video()` constructed a new MediaFileUpload and videos.insert on each transient failure, restarting the transfer and risking ambiguous retries after lost server response.
- Small-file uploads used `request.execute()` despite `resumable=True`; they had no reusable request for transient failures.
- `StateManager.set_upload_state(filepath, 'uploading')` discarded retry counters, causing repeated “attempt 2/3” messages.
- Manual and watch uploads could race using the same UploadManager instance.

## Implementation

- Classify SSL EOF and common transient socket errors, but do **not** classify certificate verification failures as transient.
- Route all resumable uploads through `next_chunk()`, preserving one upload request/session during transient attempts, including the one-chunk case. Fast retries run on the same request so library-managed resumable URI/progress can survive network interruptions.
- Respect YouTube quota errors without misclassifying them as transient. After retry exhaustion or non-transient errors, schedule persistent retries as before.
- Preserve failure count when upload state changes from failed to uploading/pending; clear retry metadata on completed. Do not alter existing upload history.
- Use a per-UploadManager RLock around upload operations, preventing two threads within the same process from uploading the same file simultaneously.
- Tests use fakes and verify same-request continuation, SSL EOF classification, progress callback, persistent retry counter, quota handling and error classification.

## Limitations

The resumable URI is not persisted across app restarts; recovery is within an active process. Concurrent processes have no cross-process upload lock, and an ambiguous server response requires careful API verification on real uploads. Retrying an already-completed upload is still possible if a server loses the resumable session and upload history was not recorded. Test with a disposable YouTube account before relying on unattended bulk uploads.

## Validation requirements

```bash
python -m pytest tests/test_upload_manager.py tests/test_state_manager.py -q
python -m pytest -q
git diff --check
```

Inspect the Windows and Ubuntu CI matrix on this PR. Test an intentionally interrupted resumable upload on a safe test account (not required for unit CI) and confirm the same session continues where the API permits.

This handoff was prepared through GitHub without a local checkout; **no local tests were executed by ChatGPT**. Record exact CI runs and test outputs before calling the task verified.
