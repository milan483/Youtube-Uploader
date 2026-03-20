import os
import sys
from types import SimpleNamespace

import config

from services.batch_uploader import BatchUploader


class FakeFileHandler:
    def __init__(self, files):
        self.files = list(files)

    def get_video_files(self, folder_path):
        return list(self.files)


class FakeStateManager:
    def __init__(self, states=None, retry_ready=None, retry_info=None):
        self.states = states or {}
        self.retry_ready = retry_ready or {}
        self.retry_info = retry_info or {}

    def get_upload_state(self, filepath):
        return self.states.get(filepath)

    def is_ready_for_retry(self, filepath):
        return self.retry_ready.get(filepath, True)

    def get_retry_info(self, filepath):
        return self.retry_info.get(filepath, {"retry_count": 0, "next_retry_time": None})


class FakeUploadManager:
    def __init__(self, outcomes, state_manager=None, refresh_needed=False):
        self._outcomes = list(outcomes)
        self.state_manager = state_manager
        self._refresh_needed = refresh_needed
        self.upload_calls = []

    def needs_client_refresh(self):
        return self._refresh_needed

    def upload_video(self, filepath, progress_callback=None):
        self.upload_calls.append(filepath)
        if not self._outcomes:
            raise AssertionError("No outcome configured for upload call")

        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def install_fake_quota_error(monkeypatch):
    class FakeQuotaExceededError(Exception):
        pass

    monkeypatch.setitem(
        sys.modules,
        "upload_manager",
        SimpleNamespace(QuotaExceededError=FakeQuotaExceededError),
    )
    return FakeQuotaExceededError


def test_upload_folder_calls_on_no_files_when_directory_is_empty(monkeypatch):
    install_fake_quota_error(monkeypatch)
    no_files_called = {"value": False}
    uploader = BatchUploader(FakeUploadManager(outcomes=[]), FakeFileHandler(files=[]))

    results = uploader.upload_folder(
        "/watch",
        callbacks={"on_no_files": lambda: no_files_called.update(value=True)},
    )

    assert no_files_called["value"] is True
    assert results["total_files"] == 0
    assert results["success_count"] == 0


def test_upload_folder_handles_exhausted_and_deferred_retry_states(monkeypatch):
    install_fake_quota_error(monkeypatch)
    folder = "/watch"
    file_a = os.path.join(folder, "a.mp4")
    file_b = os.path.join(folder, "b.mp4")
    file_c = os.path.join(folder, "c.mp4")

    state_manager = FakeStateManager(
        states={
            file_a: "failed",
            file_b: "failed",
            file_c: "pending",
        },
        retry_ready={
            file_a: False,
            file_b: False,
            file_c: True,
        },
        retry_info={
            file_a: {"retry_count": config.MAX_UPLOAD_RETRY_ATTEMPTS, "next_retry_time": None},
            file_b: {"retry_count": 1, "next_retry_time": "2099-01-01T12:00:00"},
            file_c: {"retry_count": 0, "next_retry_time": None},
        },
    )

    upload_manager = FakeUploadManager(
        outcomes=[(True, "Uploaded", "vid-1")],
        state_manager=state_manager,
    )
    uploader = BatchUploader(upload_manager, FakeFileHandler(files=["a.mp4", "b.mp4", "c.mp4"]))
    file_results = []

    results = uploader.upload_folder(
        folder,
        callbacks={"on_file_result": lambda success, message, filepath, video_id: file_results.append((success, message, filepath, video_id))},
    )

    assert results["total_files"] == 3
    assert results["success_count"] == 1
    assert results["skip_count"] == 1
    assert results["fail_count"] == 1
    assert len(upload_manager.upload_calls) == 1
    assert any("manual intervention required" in message.lower() for _, message, _, _ in file_results)
    assert any("retry scheduled" in message.lower() for _, message, _, _ in file_results)


def test_upload_folder_stops_batch_on_quota_exceeded(monkeypatch):
    quota_error = install_fake_quota_error(monkeypatch)
    folder = "/watch"
    quota_notified = {"value": False}

    upload_manager = FakeUploadManager(
        outcomes=[quota_error("quota"), (True, "Uploaded", "vid-2")],
        state_manager=None,
    )
    uploader = BatchUploader(upload_manager, FakeFileHandler(files=["a.mp4", "b.mp4"]))

    results = uploader.upload_folder(
        folder,
        callbacks={"on_quota_exceeded": lambda: quota_notified.update(value=True)},
    )

    assert results["quota_exceeded"] is True
    assert quota_notified["value"] is True
    assert len(upload_manager.upload_calls) == 1


def test_upload_folder_cancels_before_processing_when_should_stop_is_true(monkeypatch):
    install_fake_quota_error(monkeypatch)
    cancelled = {"value": False}
    upload_manager = FakeUploadManager(outcomes=[(True, "Uploaded", "vid-1")], state_manager=None)
    uploader = BatchUploader(upload_manager, FakeFileHandler(files=["a.mp4"]))

    results = uploader.upload_folder(
        "/watch",
        callbacks={"on_batch_cancelled": lambda: cancelled.update(value=True)},
        should_stop=lambda: True,
    )

    assert cancelled["value"] is True
    assert results["total_files"] == 1
    assert upload_manager.upload_calls == []


def test_upload_folder_classifies_retry_scheduled_message_as_skip(monkeypatch):
    install_fake_quota_error(monkeypatch)
    upload_manager = FakeUploadManager(
        outcomes=[(False, "Retry scheduled after 2099-01-01 12:00:00; skipping for now.", None)],
        state_manager=None,
    )
    uploader = BatchUploader(upload_manager, FakeFileHandler(files=["a.mp4"]))

    results = uploader.upload_folder("/watch")

    assert results["skip_count"] == 1
    assert results["fail_count"] == 0
