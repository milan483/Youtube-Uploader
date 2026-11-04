import io
import os
import ssl

import pytest

import upload_manager as upload_manager_module
from upload_manager import QuotaExceededError, UploadManager


class DummyMediaFileUpload:
    def __init__(self, *args, **kwargs):
        self._fd = io.BytesIO()


class SequencedRequest:
    def __init__(self, outcomes):
        self.outcomes = outcomes
        self.chunk_calls = 0

    def next_chunk(self):
        self.chunk_calls += 1
        if not self.outcomes:
            raise AssertionError("No configured outcomes left")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        if isinstance(outcome, tuple):
            return outcome
        return None, outcome


class SequencedYouTube:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.insert_calls = []
        self.requests = []

    def videos(self):
        return self

    def insert(self, **kwargs):
        self.insert_calls.append(kwargs)
        request = SequencedRequest(self.outcomes)
        self.requests.append(request)
        return request


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


def test_watch_upload_archives_under_root_preserving_relative_parent(monkeypatch, tmp_path):
    manager, _, youtube, file_handler, state_manager = build_upload_manager(
        monkeypatch,
        tmp_path,
        outcomes=[{"id": "nested-1"}],
    )
    watch_root = tmp_path / "watch"
    source = watch_root / "Games" / "Rain World" / "clip.mp4"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"nested-video")

    success, _, video_id = manager.upload_video(str(source), watch_root=str(watch_root))

    assert success is True
    assert video_id == "nested-1"
    assert file_handler.safe_move_calls == [
        (str(source), str(watch_root / "Uploaded" / "Games" / "Rain World" / "clip.mp4"), "abc123")
    ]
    assert file_handler.created_directories == [str(watch_root / "Uploaded" / "Games" / "Rain World")]
    assert youtube.insert_calls
    assert state_manager.history_calls == [("abc123", "clip.mp4", "nested-1")]


def test_watch_upload_rejects_unsafe_source_before_hash_state_or_network(monkeypatch, tmp_path):
    manager, filepath, youtube, file_handler, state_manager = build_upload_manager(
        monkeypatch,
        tmp_path,
        outcomes=[{"id": "unused"}],
    )
    hash_calls = []
    original_hash = file_handler.compute_file_hash
    file_handler.compute_file_hash = lambda path: (hash_calls.append(path), original_hash(path))[1]
    monkeypatch.setattr(
        upload_manager_module.FileHandler,
        "is_safe_watch_file",
        staticmethod(lambda path, root: False),
        raising=False,
    )

    success, message, video_id = manager.upload_video(filepath, watch_root=str(tmp_path))

    assert success is False
    assert "Unsafe" in message
    assert video_id is None
    assert hash_calls == []
    assert state_manager.set_state_calls == []
    assert youtube.insert_calls == []
    assert file_handler.safe_move_calls == []


def test_watch_upload_rejects_symlinked_archive_before_network(monkeypatch, tmp_path):
    manager, _, youtube, file_handler, state_manager = build_upload_manager(
        monkeypatch,
        tmp_path,
        outcomes=[{"id": "unused"}],
    )
    watch_root = tmp_path / "watch"
    source = watch_root / "clip.mp4"
    source.parent.mkdir()
    source.write_bytes(b"video")
    outside = tmp_path / "outside"
    outside.mkdir()
    (watch_root / "Uploaded").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(
        upload_manager_module.FileHandler,
        "is_safe_watch_file",
        staticmethod(lambda path, root: True),
        raising=False,
    )

    success, message, video_id = manager.upload_video(str(source), watch_root=str(watch_root))

    assert success is False
    assert "Unsafe archive" in message
    assert video_id is None
    assert youtube.insert_calls == []
    assert state_manager.set_state_calls == []
    assert file_handler.safe_move_calls == []
    assert source.read_bytes() == b"video"


def test_watch_upload_preserves_original_when_archive_move_fails(monkeypatch, tmp_path):
    manager, _, _, file_handler, _ = build_upload_manager(
        monkeypatch,
        tmp_path,
        outcomes=[{"id": "uploaded"}],
        file_handler=FakeFileHandler(safe_move_result=(False, "copy verification failed")),
    )
    watch_root = tmp_path / "watch"
    source = watch_root / "Subdir" / "clip.mp4"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"original")

    success, _, _ = manager.upload_video(str(source), watch_root=str(watch_root))

    assert success is True  # YouTube succeeded; the archive move is a warning.
    assert source.read_bytes() == b"original"
    assert file_handler.safe_move_calls == [
        (str(source), str(watch_root / "Uploaded" / "Subdir" / "clip.mp4"), "abc123")
    ]


def test_watch_upload_keeps_manual_upload_sibling_archive_compatibility(monkeypatch, tmp_path):
    manager, filepath, _, file_handler, _ = build_upload_manager(
        monkeypatch,
        tmp_path,
        outcomes=[{"id": "manual-1"}],
    )

    success, _, _ = manager.upload_video(filepath)

    assert success is True
    assert file_handler.safe_move_calls == [
        (filepath, str(tmp_path / "Uploaded" / "video.mp4"), "abc123")
    ]


def test_watch_upload_accepts_relative_source_and_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    manager, _, _, file_handler, _ = build_upload_manager(
        monkeypatch,
        tmp_path,
        outcomes=[{"id": "relative-1"}],
    )
    source = tmp_path / "watch" / "Subdir" / "clip.mp4"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"video")

    success, _, video_id = manager.upload_video(
        os.path.join("watch", "Subdir", "clip.mp4"),
        watch_root="watch",
    )

    assert success is True
    assert video_id == "relative-1"
    assert file_handler.safe_move_calls == [
        (os.path.join("watch", "Subdir", "clip.mp4"),
         os.path.join("watch", "Uploaded", "Subdir", "clip.mp4"), "abc123")
    ]


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
    assert len(youtube.insert_calls) == 1
    assert youtube.requests[0].chunk_calls == 2
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


def test_nested_uploads_with_real_file_handler_archive_once_without_rediscovery(monkeypatch, tmp_path):
    from file_handler import FileHandler

    handler = FileHandler()
    manager, _, youtube, _, state = build_upload_manager(
        monkeypatch, tmp_path, outcomes=[{"id": "first"}, {"id": "second"}], file_handler=handler)
    root = tmp_path / "watch"
    for parent, payload in (("Game A", b"first clip"), ("Game B", b"second clip")):
        source = root / parent / "clip.mp4"
        source.parent.mkdir(parents=True)
        source.write_bytes(payload)

    paths = handler.get_video_files(str(root), recursive=True)
    assert paths == [os.path.join("Game A", "clip.mp4"), os.path.join("Game B", "clip.mp4")]
    for relative in paths:
        success, _, _ = manager.upload_video(str(root / relative), watch_root=str(root))
        assert success
        assert not (root / relative).exists()

    assert (root / "Uploaded" / "Game A" / "clip.mp4").read_bytes() == b"first clip"
    assert (root / "Uploaded" / "Game B" / "clip.mp4").read_bytes() == b"second clip"
    assert handler.get_video_files(str(root), recursive=True) == []
    assert len(youtube.insert_calls) == len(state.history_calls) == 2


def test_watch_upload_rejects_junction_like_archive_before_network(monkeypatch, tmp_path):
    from file_handler import FileHandler

    manager, _, youtube, _, _ = build_upload_manager(
        monkeypatch, tmp_path, outcomes=[{"id": "unused"}])
    source = tmp_path / "watch" / "clip.mp4"
    source.parent.mkdir()
    source.write_bytes(b"clip")
    archive = source.parent / "Uploaded"
    archive.mkdir()
    original_guard = FileHandler._is_link_or_junction
    monkeypatch.setattr(FileHandler, "_is_link_or_junction", staticmethod(
        lambda path: os.fspath(path) == str(archive) or original_guard(path)))

    success, message, _ = manager.upload_video(str(source), watch_root=str(source.parent))

    assert not success
    assert "Unsafe archive" in message
    assert youtube.insert_calls == []
    assert source.read_bytes() == b"clip"


def test_ssl_eof_recovers_in_same_resumable_session(monkeypatch, tmp_path):
    error = ssl.SSLEOFError(8, "EOF occurred in violation of protocol (_ssl.c:2396)")
    manager, filepath, youtube, _, state = build_upload_manager(
        monkeypatch, tmp_path, outcomes=[error, {"id": "eof-recovered"}]
    )

    success, _, video_id = manager.upload_video(filepath)

    assert success is True and video_id == "eof-recovered"
    assert manager._is_transient_network_error(error)
    assert len(youtube.insert_calls) == 1
    assert youtube.requests[0].chunk_calls == 2
    assert state.history_calls == [("abc123", "video.mp4", "eof-recovered")]


def test_chunk_progress_and_resume_keep_same_request(monkeypatch, tmp_path):
    class Progress:
        def __init__(self, fraction):
            self.fraction = fraction

        def progress(self):
            return self.fraction

    manager, filepath, youtube, _, _ = build_upload_manager(
        monkeypatch,
        tmp_path,
        outcomes=[
            (Progress(0.25), None),
            ConnectionResetError("connection reset by peer"),
            (Progress(0.75), None),
            {"id": "recovered"},
        ],
    )
    progress = []

    success, _, video_id = manager.upload_video(filepath, progress_callback=progress.append)

    assert success and video_id == "recovered"
    assert progress == [25, 75]
    assert len(youtube.insert_calls) == 1
    assert youtube.requests[0].chunk_calls == 4


def test_scheduled_failure_does_not_reset_existing_retry_count(monkeypatch, tmp_path):
    manager, filepath, youtube, _, state = build_upload_manager(
        monkeypatch, tmp_path, outcomes=[Exception("backend unavailable")],
        state_manager=FakeStateManager(retry_counts={str(tmp_path / "video.mp4"): 2}),
    )

    success, message, _ = manager.upload_video(filepath)

    assert not success
    assert "manual intervention required" in message.lower()
    assert state.set_state_calls[-1]["retry_count"] == 3
    assert len(youtube.insert_calls) == 1


def test_tls_certificate_errors_are_not_mistaken_for_transient_eof(monkeypatch, tmp_path):
    error = ssl.SSLCertVerificationError("certificate verify failed")
    manager, filepath, youtube, _, _ = build_upload_manager(
        monkeypatch, tmp_path, outcomes=[error]
    )

    success, _, _ = manager.upload_video(filepath)

    assert not success
    assert not manager._is_transient_network_error(error)
    assert len(youtube.insert_calls) == 1
    assert youtube.requests[0].chunk_calls == 1
