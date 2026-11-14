import pytest

from utils.retry_settings import (
    DEFAULT_RETRY_SETTINGS,
    effective_retry_settings,
    validate_retry_settings,
)


@pytest.mark.parametrize('updates', [
    {'max_upload_retry_attempts': True},
    {'max_upload_retry_attempts': 0},
    {'max_upload_retry_attempts': 101},
    {'initial_retry_delay_seconds': 1.5},
    {'initial_retry_delay_seconds': 0},
    {'max_retry_delay_seconds': 86401},
    {'initial_retry_delay_seconds': 120, 'max_retry_delay_seconds': 60},
])
def test_validation_rejects_invalid_values(updates):
    with pytest.raises(ValueError):
        validate_retry_settings({**DEFAULT_RETRY_SETTINGS, **updates})


def test_bad_saved_fields_use_safe_defaults_without_dropping_valid_fields():
    values = effective_retry_settings({
        'max_upload_retry_attempts': 8,
        'initial_retry_delay_seconds': False,
        'max_retry_delay_seconds': 1.25,
    })
    assert values == {**DEFAULT_RETRY_SETTINGS, 'max_upload_retry_attempts': 8}


def test_bad_saved_cross_field_pair_resets_delay_pair():
    values = effective_retry_settings({
        'max_upload_retry_attempts': 8,
        'initial_retry_delay_seconds': 800,
        'max_retry_delay_seconds': 200,
    })
    assert values == {**DEFAULT_RETRY_SETTINGS, 'max_upload_retry_attempts': 8}
