import config
from utils.logging import LoggerMixin


class UploadStateStore(LoggerMixin):
    def __init__(self, json_store, logger=None):
        self.json_store = json_store
        self.logger = logger

    def load(self):
        return self.json_store.load_json_with_validation(
            config.UPLOAD_STATE_FILE,
            self._validate_schema
        )

    def save(self, data):
        self.json_store.atomic_write_json(config.UPLOAD_STATE_FILE, data)

    def _validate_schema(self, data):
        if not isinstance(data, dict):
            return False

        valid_states = ['pending', 'uploading', 'completed', 'failed']

        for filepath, state_info in data.items():
            if not isinstance(state_info, dict):
                self._log(f"Invalid upload_state entry: {filepath} (not a dict)")
                return False

            if 'state' not in state_info or 'timestamp' not in state_info:
                self._log(f"Invalid upload_state entry: {filepath} (missing keys)")
                return False

            if state_info['state'] not in valid_states:
                self._log(f"Invalid upload_state entry: {filepath} (invalid state)")
                return False

            if 'retry_count' in state_info and not isinstance(state_info['retry_count'], int):
                self._log(f"Invalid upload_state entry: {filepath} (retry_count not an int)")
                return False

        return True
