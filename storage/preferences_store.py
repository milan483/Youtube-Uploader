import config
from utils.logging import LoggerMixin
from utils.retry_settings import RETRY_SETTING_KEYS, effective_retry_settings


class PreferencesStore(LoggerMixin):
    def __init__(self, json_store, logger=None):
        self.json_store = json_store
        self.logger = logger

    def load(self):
        saved = self.json_store.load_json_with_validation(
            config.USER_PREFERENCES_FILE,
            self._validate_schema
        )
        # Repair malformed retry fields without losing unrelated preferences.
        if not isinstance(saved, dict):
            return {}
        effective = effective_retry_settings(saved)
        for key in RETRY_SETTING_KEYS:
            if key in saved:
                saved[key] = effective[key]
        return saved

    def save(self, data):
        self.json_store.atomic_write_json(config.USER_PREFERENCES_FILE, data)

    def _validate_schema(self, data):
        if not isinstance(data, dict):
            return False

        optional_string_fields = ['last_watch_folder', 'privacy_setting', 'playlist_title', 'video_category']
        optional_bool_fields = ['autonomous_mode', 'auto_start_watching', 'start_minimized',
                               'scan_subdirectories', 'delete_after_upload',
                               'notify_when_empty', 'auto_close_when_empty', 'start_with_windows',
                               'start_on_login',
                               'notify_upload_success', 'notify_upload_failed', 'notify_quota_exceeded',
                               'notify_batch_complete']

        # Retry fields are sanitized by load() instead of rejecting the entire
        # preference document when one retry field is malformed.

        for field in optional_string_fields:
            if field in data and not isinstance(data[field], str):
                self._log(f"Invalid user_preferences: {field} not a string")
                return False

        for field in optional_bool_fields:
            if field in data and not isinstance(data[field], bool):
                self._log(f"Invalid user_preferences: {field} not a boolean")
                return False

        return True
