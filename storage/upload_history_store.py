import config
from utils.logging import LoggerMixin


class UploadHistoryStore(LoggerMixin):
    def __init__(self, json_store, logger=None):
        self.json_store = json_store
        self.logger = logger

    def load(self):
        return self.json_store.load_json_with_validation(
            config.UPLOAD_HISTORY_FILE,
            self._validate_schema
        )

    def save(self, data):
        self.json_store.atomic_write_json(config.UPLOAD_HISTORY_FILE, data)

    def _validate_schema(self, data):
        if not isinstance(data, dict):
            return False

        for hash_key, metadata in data.items():
            if not isinstance(metadata, dict):
                self._log(f"Invalid upload_history entry: {hash_key} (not a dict)")
                return False

            required_keys = ['filename', 'upload_date', 'video_id']
            if not all(key in metadata for key in required_keys):
                self._log(f"Invalid upload_history entry: {hash_key} (missing keys)")
                return False

        return True
