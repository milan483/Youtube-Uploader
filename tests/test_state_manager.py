from datetime import datetime, timedelta
from pathlib import Path

import config
import pytest

from state_manager import StateManager


def configure_state_files(monkeypatch, tmp_path):
    state_paths = {
        "UPLOAD_HISTORY_FILE": tmp_path / "upload_history.json",
        "UPLOAD_STATE_FILE": tmp_path / "upload_state.json",
        "QUOTA_STATE_FILE": tmp_path / "quota_state.json",
        "PLAYLIST_SORT_STATE_FILE": tmp_path / "playlist_sort_state.json",
        "USER_PREFERENCES_FILE": tmp_path / "user_preferences.json",
    }

    for key, path in state_paths.items():
        monkeypatch.setattr(config, key, str(path))

    return state_paths


@pytest.fixture
def configured_state_files(monkeypatch, tmp_path):
    return configure_state_files(monkeypatch, tmp_path)


def test_initializes_empty_state_when_files_missing(configured_state_files):
    manager = StateManager()

    assert manager.upload_history == {}
    assert manager.upload_states == {}
    assert manager.quota_state == {}
    assert manager.playlist_sort_state == {}


def test_corrupted_history_creates_backup_and_resets(configured_state_files):
    history_path = Path(config.UPLOAD_HISTORY_FILE)
    history_path.write_text("{invalid json", encoding="utf-8")

    manager = StateManager()
    backups = list(history_path.parent.glob("upload_history.json.corrupt.*"))

    assert manager.upload_history == {}
    assert backups, "Expected corrupted history backup to be created"
    assert not history_path.exists()


def test_is_ready_for_retry_respects_time_and_retry_limit(configured_state_files):
    manager = StateManager()
    future_time = (datetime.now() + timedelta(minutes=10)).isoformat()
    past_time = (datetime.now() - timedelta(minutes=10)).isoformat()
    future_path = "/tmp/future.mp4"
    past_path = "/tmp/past.mp4"
    exhausted_path = "/tmp/exhausted.mp4"

    manager.upload_states = {
        future_path: {"state": "failed", "retry_count": 1, "next_retry_time": future_time},
        past_path: {"state": "failed", "retry_count": 1, "next_retry_time": past_time},
        exhausted_path: {"state": "failed", "retry_count": config.MAX_UPLOAD_RETRY_ATTEMPTS},
    }

    assert not manager.is_ready_for_retry(future_path)
    assert manager.is_ready_for_retry(past_path)
    assert not manager.is_ready_for_retry(exhausted_path)


def test_reset_incomplete_uploads_to_pending_only_for_existing_files(configured_state_files, tmp_path):
    manager = StateManager()
    existing_file = tmp_path / "existing.mp4"
    existing_file.write_bytes(b"data")
    missing_file = tmp_path / "missing.mp4"

    manager.upload_states = {
        str(existing_file): {"state": "uploading", "timestamp": "2026-01-01T00:00:00"},
        str(missing_file): {"state": "uploading", "timestamp": "2026-01-01T00:00:00"},
    }

    reset_count = manager.reset_incomplete_uploads_to_pending()

    assert reset_count == 1
    assert manager.get_upload_state(str(existing_file)) == "pending"
    assert manager.get_upload_state(str(missing_file)) == "uploading"
