import os
import sys
from types import SimpleNamespace

import config
import pytest

from services.batch_uploader import BatchUploader


class FakeFileHandler:
    def __init__(self, files):
        self.files = list(files)

    def get_video_files(self, folder_path, recursive=False):
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
        self.watch_roots = []

    def needs_client_refresh(self):
        return self._refresh_needed

    def upload_video(self, filepath, progress_callback=None, watch_root=None):
        self.upload_calls.append(filepath)
        self.watch_roots.append(watch_root)
        if not self._outcomes:
            raise AssertionError("No outcome configured for upload call")

        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def watch_folder(tmp_path):
    for name in ("a.mp4", "b.mp4", "c.mp4"):
        (tmp_path / name).write_bytes(name.encode())
    return str(tmp_path)


def install_fake_quota_error(monkeypatch):
    class FakeQuotaExceededError(Exception):
        pass

    monkeypatch.setitem(
        sys.modules,
        "upload_manager",
        SimpleNamespace(QuotaExceededError=FakeQuotaExceededError),
    )
    return FakeQuotaExceededError


def test_upload_folder_calls_on_no_files_when_directory_is_empty(monkeypatch, watch_folder):
    install_fake_quota_error(monkeypatch)
    no_files_called = {"value": False}
    uploader = BatchUploader(FakeUploadManager(outcomes=[]), FakeFileHandler(files=[]))

    results = uploader.upload_folder(
        watch_folder,
        callbacks={"on_no_files": lambda: no_files_called.update(value=True)},
    )

    assert no_files_called["value"] is True
    assert results["total_files"] == 0
    assert results["success_count"] == 0


def test_upload_folder_handles_exhausted_and_deferred_retry_states(monkeypatch, watch_folder):
    install_fake_quota_error(monkeypatch)
    folder = watch_folder
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


def test_upload_folder_stops_batch_on_quota_exceeded(monkeypatch, watch_folder):
    quota_error = install_fake_quota_error(monkeypatch)
    folder = watch_folder
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


def test_upload_folder_cancels_before_processing_when_should_stop_is_true(monkeypatch, watch_folder):
    install_fake_quota_error(monkeypatch)
    cancelled = {"value": False}
    upload_manager = FakeUploadManager(outcomes=[(True, "Uploaded", "vid-1")], state_manager=None)
    uploader = BatchUploader(upload_manager, FakeFileHandler(files=["a.mp4"]))

    results = uploader.upload_folder(
        watch_folder,
        callbacks={"on_batch_cancelled": lambda: cancelled.update(value=True)},
        should_stop=lambda: True,
    )

    assert cancelled["value"] is True
    assert results["total_files"] == 1
    assert upload_manager.upload_calls == []


def test_upload_folder_classifies_retry_scheduled_message_as_skip(monkeypatch, watch_folder):
    install_fake_quota_error(monkeypatch)
    upload_manager = FakeUploadManager(
        outcomes=[(False, "Retry scheduled after 2099-01-01 12:00:00; skipping for now.", None)],
        state_manager=None,
    )
    uploader = BatchUploader(upload_manager, FakeFileHandler(files=["a.mp4"]))

    results = uploader.upload_folder(watch_folder)

    assert results["skip_count"] == 1
    assert results["fail_count"] == 0


def test_recursive_discovery_passes_relative_sources_and_watch_root(tmp_path, monkeypatch):
    from file_handler import FileHandler

    install_fake_quota_error(monkeypatch)
    for name in ("Game A/clip.mp4", "Game B/clip.mp4", "loose.mp4", "Uploaded/old.mp4"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(name.encode())
    manager = FakeUploadManager([(True, "Uploaded", "video")] * 3)
    uploader = BatchUploader(manager, FileHandler())

    result = uploader.upload_folder(str(tmp_path), recursive=True)

    assert result["success_count"] == 3
    assert manager.upload_calls == [str(tmp_path / name) for name in
                                    ("Game A/clip.mp4", "Game B/clip.mp4", "loose.mp4")]
    assert manager.watch_roots == [str(tmp_path)] * 3


def test_default_batch_scan_remains_top_level(tmp_path, monkeypatch):
    from file_handler import FileHandler

    install_fake_quota_error(monkeypatch)
    (tmp_path / "top.mp4").write_bytes(b"top")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "other.mp4").write_bytes(b"other")
    manager = FakeUploadManager([(True, "Uploaded", "video")])

    BatchUploader(manager, FileHandler()).upload_folder(str(tmp_path))

    assert manager.upload_calls == [str(tmp_path / "top.mp4")]
    assert manager.watch_roots == [str(tmp_path)]


def test_batch_rejects_untrusted_discovery_entries_before_upload(tmp_path, monkeypatch):
    install_fake_quota_error(monkeypatch)
    root = tmp_path / "watch"
    root.mkdir()
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"outside")
    (root / "Uploaded").mkdir()
    (root / "Uploaded" / "old.mp4").write_bytes(b"old")
    (root / "link.mp4").symlink_to(outside)
    unsafe = ["../outside.mp4", str(outside), "Uploaded/old.mp4", "link.mp4",
              "missing.mp4", "C:\\outside.mp4", "..\\outside.mp4"]
    manager = FakeUploadManager([])

    result = BatchUploader(manager, FakeFileHandler(unsafe)).upload_folder(str(root), recursive=True)

    assert manager.upload_calls == []
    assert result["total_files"] == 0


def test_batch_revalidates_sources_after_discovery(tmp_path, monkeypatch):
    install_fake_quota_error(monkeypatch)
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"clip")
    manager = FakeUploadManager([])

    result = BatchUploader(manager, FakeFileHandler(["clip.mp4"])).upload_folder(
        str(tmp_path), callbacks={"on_batch_found": lambda count: source.unlink()})

    assert manager.upload_calls == []
    assert result["fail_count"] == 1
