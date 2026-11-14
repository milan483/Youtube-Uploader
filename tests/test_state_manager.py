import json
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
    assert manager.get_all_preferences()["scan_subdirectories"] is False


def test_scan_subdirectories_preference_persists_and_reloads(configured_state_files):
    manager = StateManager()
    manager.set_preference("scan_subdirectories", True)

    reloaded_manager = StateManager()

    assert reloaded_manager.get_preference("scan_subdirectories") is True
    assert reloaded_manager.get_all_preferences()["scan_subdirectories"] is True


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


def test_retry_count_survives_uploading_and_pending_transitions(configured_state_files):
    manager = StateManager()
    filepath = "/tmp/retrying.mp4"
    manager.set_upload_state(
        filepath, "failed", retry_count=2,
        next_retry_time=(datetime.now() - timedelta(minutes=10)).isoformat()
    )
    assert manager.get_retry_count(filepath) == 2
    assert manager.is_ready_for_retry(filepath)

    manager.set_upload_state(filepath, "uploading")
    assert manager.get_retry_count(filepath) == 2
    assert manager.get_retry_info(filepath)["next_retry_time"] is None

    manager.set_upload_state(filepath, "pending")
    assert manager.get_retry_count(filepath) == 2

    manager.set_upload_state(filepath, "completed")
    assert manager.get_retry_count(filepath) == 0
    assert manager.get_retry_info(filepath)["next_retry_time"] is None


@pytest.mark.parametrize("existing_preferences", [None, '{"scan_subdirectories": true}'])
def test_delete_after_upload_defaults_off_and_persists(configured_state_files, existing_preferences):
    if existing_preferences is not None:
        configured_state_files["USER_PREFERENCES_FILE"].write_text(existing_preferences, encoding="utf-8")
    manager = StateManager()
    assert manager.get_all_preferences()["delete_after_upload"] is False

    manager.set_preference("delete_after_upload", True)
    assert StateManager().get_all_preferences()["delete_after_upload"] is True


def test_non_boolean_delete_after_upload_is_rejected(configured_state_files):
    configured_state_files["USER_PREFERENCES_FILE"].write_text(
        '{"delete_after_upload": "true"}', encoding="utf-8"
    )
    assert StateManager().get_all_preferences()["delete_after_upload"] is False


def test_retry_settings_defaults_and_persistence(configured_state_files):
    manager = StateManager()
    assert manager.get_retry_settings() == {
        'max_upload_retry_attempts': 3,
        'initial_retry_delay_seconds': 60,
        'max_retry_delay_seconds': 3600,
    }

    manager.set_preference('privacy_setting', 'unlisted')
    manager.set_retry_settings({
        'max_upload_retry_attempts': 7,
        'initial_retry_delay_seconds': 12,
        'max_retry_delay_seconds': 240,
    })

    reloaded = StateManager()
    assert reloaded.get_retry_settings() == manager.get_retry_settings()
    assert reloaded.get_preference('privacy_setting') == 'unlisted'


@pytest.mark.parametrize('updates', [
    {'max_upload_retry_attempts': False},
    {'max_upload_retry_attempts': 100.0},
    {'max_upload_retry_attempts': 101},
    {'initial_retry_delay_seconds': 0},
    {'max_retry_delay_seconds': 86401},
    {'initial_retry_delay_seconds': 500, 'max_retry_delay_seconds': 100},
])
def test_retry_settings_validation_is_atomic(configured_state_files, updates):
    manager = StateManager()
    before = manager.get_retry_settings()

    with pytest.raises(ValueError):
        manager.set_retry_settings({**before, **updates})

    assert manager.get_retry_settings() == before
    assert StateManager().get_retry_settings() == before


def test_retry_settings_write_failure_preserves_memory(configured_state_files, monkeypatch):
    manager = StateManager()
    before = manager.get_all_preferences()

    def fail_save(data):
        raise OSError('disk full')

    monkeypatch.setattr(manager.preferences_store, 'save', fail_save)
    with pytest.raises(OSError, match='disk full'):
        manager.set_retry_settings({
            'max_upload_retry_attempts': 5,
            'initial_retry_delay_seconds': 20,
            'max_retry_delay_seconds': 100,
        })

    assert manager.get_all_preferences() == before


def test_bad_saved_retry_fields_preserve_unrelated_preferences(configured_state_files):
    configured_state_files['USER_PREFERENCES_FILE'].write_text(json.dumps({
        'privacy_setting': 'unlisted',
        'scan_subdirectories': True,
        'max_upload_retry_attempts': True,
        'initial_retry_delay_seconds': 90000,
        'max_retry_delay_seconds': 1.5,
    }), encoding='utf-8')
    manager = StateManager()

    assert manager.get_retry_settings() == {
        'max_upload_retry_attempts': 3,
        'initial_retry_delay_seconds': 60,
        'max_retry_delay_seconds': 3600,
    }
    assert manager.get_preference('privacy_setting') == 'unlisted'
    assert manager.get_preference('scan_subdirectories') is True


def test_increasing_retry_limit_revives_exhausted_file(configured_state_files, tmp_path):
    manager = StateManager()
    source = tmp_path / 'failed.mp4'
    source.write_bytes(b'video')
    manager.set_upload_state(str(source), 'failed', retry_count=3)
    assert not manager.is_ready_for_retry(str(source))

    manager.set_retry_settings({
        'max_upload_retry_attempts': 5,
        'initial_retry_delay_seconds': 60,
        'max_retry_delay_seconds': 3600,
    })
    assert manager.is_ready_for_retry(str(source))
    assert str(source) in manager.get_failed_uploads_for_retry()


def test_retry_settings_preserve_existing_deadlines_and_allow_policy_snapshot(configured_state_files):
    manager = StateManager()
    snapshot = manager.get_retry_settings()
    deadline = (datetime.now() + timedelta(minutes=10)).isoformat()
    manager.set_upload_state('waiting.mp4', 'failed', retry_count=1, next_retry_time=deadline)
    manager.set_upload_state('exhausted.mp4', 'failed', retry_count=3)
    manager.set_retry_settings({**snapshot, 'max_upload_retry_attempts': 8})

    assert manager.get_retry_info('waiting.mp4')['next_retry_time'] == deadline
    assert not manager.is_ready_for_retry('waiting.mp4')
    assert not manager.is_ready_for_retry('exhausted.mp4', snapshot)
    assert manager.is_ready_for_retry('exhausted.mp4')
