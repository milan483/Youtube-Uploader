import io

import pytest

import upload_manager as upload_manager_module
from upload_manager import QuotaExceededError, UploadManager


class DummyMediaFileUpload:
    def __init__(self, *args, **kwargs):
        self._fd = io.BytesIO()


class SequencedRequest:
    def __init__(self, outcome):
        self.outcome = outcome

    def execute(self):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class SequencedYouTube:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.insert_calls = []

    def videos(self):
        return self

    def insert(self, **kwargs):
        self.insert_calls.append(kwargs)
        if not self.outcomes:
            raise AssertionError("No configured outcomes left")
        return SequencedRequest(self.outcomes.pop(0))


class FakeFileHandler:
    def __init__(self, file_hash="abc123", safe_move_result=(True, "ok")):
        self.file_hash = file_hash
        self.safe_move_result = safe_move_result
        self.safe_move_calls = []
        self.created_directories = []

    def compute_file_hash(self, filepath):
        return self.file_hash

    def ensure_directory_exists(self, directory):
        self.created_directories.append(directory)
        return True

    def safe_move(self, source, destination, cached_source_hash=None):
        self.safe_move_calls.append((source, destination, cached_source_hash))
        return self.safe_move_result


class FakeStateManager:
    def __init__(self, uploaded_hashes=None, retry_counts=None):
        self.uploaded_hashes = set(uploaded_hashes or [])
        self.retry_counts = dict(retry_counts or {})
        self.set_state_calls = []
        self.history_calls = []
        self.quota_hits = 0

    def is_file_uploaded(self, file_hash):
        return file_hash in self.uploaded_hashes

    def set_upload_state(self, filepath, state, retry_count=None, next_retry_time=None):
        self.set_state_calls.append(
            {
                "filepath": filepath,
                "state": state,
                "retry_count": retry_count,
                "next_retry_time": next_retry_time,
            }
        )

    def get_retry_count(self, filepath):
        return self.retry_counts.get(filepath, 0)

    def add_upload_to_history(self, file_hash, filename, video_id):
        self.history_calls.append((file_hash, filename, video_id))

    def record_quota_hit(self):
        self.quota_hits += 1

    def get_last_quota_hit(self):
        return None

    def get_upload_count(self):
        return len(self.history_calls)


def build_upload_manager(monkeypatch, tmp_path, outcomes, state_manager=None, file_handler=None):
    monkeypatch.setattr(upload_manager_module, "MediaFileUpload", DummyMediaFileUpload)
    monkeypatch.setattr(upload_manager_module, "test_youtube_api_connection", lambda yt: True)
    monkeypatch.setattr(upload_manager_module.time, "sleep", lambda seconds: None)

    filepath = tmp_path / "video.mp4"
    filepath.write_bytes(b"video-bytes")

    youtube = SequencedYouTube(outcomes)
    file_handler = file_handler or FakeFileHandler()
    state_manager = state_manager or FakeStateManager()
    manager = UploadManager(youtube, file_handler, state_manager)

    return manager, str(filepath), youtube, file_handler, state_manager


def test_upload_video_success_updates_state_and_history(monkeypatch, tmp_path):
    manager, filepath, youtube, file_handler, state_manager = build_upload_manager(
        monkeypatch,
        tmp_path,
        outcomes=[{"id": "vid-1"}],
    )

    success, message, video_id = manager.upload_video(filepath)

    assert success is True
    assert video_id == "vid-1"
    assert "Successfully uploaded" in message
    assert state_manager.set_state_calls[0]["state"] == "uploading"
    assert state_manager.set_state_calls[-1]["state"] == "completed"
    assert state_manager.history_calls == [("abc123", "video.mp4", "vid-1")]
    assert len(youtube.insert_calls) == 1
    assert file_handler.safe_move_calls


def test_upload_video_skips_duplicate_before_api_call(monkeypatch, tmp_path):
    manager, filepath, youtube, _, state_manager = build_upload_manager(
        monkeypatch,
        tmp_path,
        outcomes=[{"id": "unused"}],
        state_manager=FakeStateManager(uploaded_hashes={"abc123"}),
    )

    success, message, video_id = manager.upload_video(filepath)

    assert success is False
    assert video_id is None
    assert "already uploaded" in message.lower()
    assert youtube.insert_calls == []
    assert state_manager.set_state_calls == []


def test_upload_video_raises_quota_exceeded_and_records_quota_hit(monkeypatch, tmp_path):
    class FakeHttpError(Exception):
        def __init__(self, content):
            super().__init__("http error")
            self.content = content

    monkeypatch.setattr(upload_manager_module, "HttpError", FakeHttpError)
    manager, filepath, _, _, state_manager = build_upload_manager(
        monkeypatch,
        tmp_path,
        outcomes=[FakeHttpError("quotaExceeded")],
    )

    with pytest.raises(QuotaExceededError):
        manager.upload_video(filepath)

    assert state_manager.quota_hits == 1
    assert state_manager.set_state_calls[0]["state"] == "uploading"
    assert state_manager.set_state_calls[-1]["state"] == "failed"


def test_upload_video_non_transient_error_schedules_retry(monkeypatch, tmp_path):
    manager, filepath, _, _, state_manager = build_upload_manager(
        monkeypatch,
        tmp_path,
        outcomes=[Exception("backend unavailable")],
    )

    success, message, video_id = manager.upload_video(filepath)
    failed_call = state_manager.set_state_calls[-1]

    assert success is False
    assert video_id is None
    assert "Will retry" in message
    assert failed_call["state"] == "failed"
    assert failed_call["retry_count"] == 1
    assert failed_call["next_retry_time"] is not None


def test_upload_video_retries_transient_error_then_succeeds(monkeypatch, tmp_path):
    manager, filepath, youtube, _, state_manager = build_upload_manager(
        monkeypatch,
        tmp_path,
        outcomes=[
            Exception("connection reset by peer"),
            {"id": "vid-2"},
        ],
    )

    success, _, video_id = manager.upload_video(filepath)
    failed_states = [call for call in state_manager.set_state_calls if call["state"] == "failed"]

    assert success is True
    assert video_id == "vid-2"
    assert len(youtube.insert_calls) == 2
    assert failed_states == []


def test_upload_video_rejects_file_over_size_limit(monkeypatch, tmp_path):
    manager, filepath, youtube, _, _ = build_upload_manager(
        monkeypatch,
        tmp_path,
        outcomes=[{"id": "unused"}],
    )
    monkeypatch.setattr(upload_manager_module.config, "MAX_FILE_SIZE_BYTES", 1)

    success, message, video_id = manager.upload_video(filepath)

    assert success is False
    assert video_id is None
    assert "File too large" in message
    assert youtube.insert_calls == []
