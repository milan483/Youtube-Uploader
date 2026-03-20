import json
from pathlib import Path

import pytest

from storage.json_store import JsonStore
from storage.playlist_sort_store import PlaylistSortStore
from storage.preferences_store import PreferencesStore
from storage.quota_state_store import QuotaStateStore
from storage.upload_history_store import UploadHistoryStore
from storage.upload_state_store import UploadStateStore


def test_atomic_write_json_persists_payload(tmp_path):
    store = JsonStore()
    target = tmp_path / "state.json"
    payload = {"a": 1, "nested": {"ok": True}}

    store.atomic_write_json(str(target), payload)

    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8")) == payload


def test_load_json_with_validation_handles_corruption_and_creates_backup(tmp_path):
    store = JsonStore()
    target = tmp_path / "broken.json"
    target.write_text("{not-valid-json", encoding="utf-8")

    loaded = store.load_json_with_validation(str(target))
    backups = list(tmp_path.glob("broken.json.corrupt.*"))

    assert loaded == {}
    assert backups
    assert not target.exists()


def test_load_json_with_validation_returns_empty_on_schema_failure(tmp_path):
    store = JsonStore()
    target = tmp_path / "payload.json"
    target.write_text(json.dumps({"field": "value"}), encoding="utf-8")

    loaded = store.load_json_with_validation(str(target), schema_validator=lambda data: False)

    assert loaded == {}


@pytest.mark.parametrize(
    "store_cls,valid_payload,invalid_payload",
    [
        (
            UploadHistoryStore,
            {"abc": {"filename": "clip.mp4", "upload_date": "2026-01-01T00:00:00", "video_id": "vid1"}},
            {"abc": {"filename": "clip.mp4", "upload_date": "2026-01-01T00:00:00"}},
        ),
        (
            UploadStateStore,
            {"/tmp/clip.mp4": {"state": "failed", "timestamp": "2026-01-01T00:00:00", "retry_count": 1}},
            {"/tmp/clip.mp4": {"state": "failed", "timestamp": "2026-01-01T00:00:00", "retry_count": "1"}},
        ),
        (
            QuotaStateStore,
            {"last_quota_hit": "2026-01-01T00:00:00"},
            {"last_quota_hit": 123},
        ),
        (
            PlaylistSortStore,
            {"playlist_id": "PL123", "sorted_items": [{"id": "x"}], "last_position": 0},
            {"playlist_id": "PL123", "sorted_items": "not-a-list", "last_position": 0},
        ),
        (
            PreferencesStore,
            {"privacy_setting": "private", "notify_quota_exceeded": True},
            {"privacy_setting": "private", "notify_quota_exceeded": "true"},
        ),
    ],
)
def test_schema_validators_accept_valid_and_reject_invalid(store_cls, valid_payload, invalid_payload):
    store = store_cls(JsonStore())

    assert store._validate_schema(valid_payload) is True
    assert store._validate_schema(invalid_payload) is False
