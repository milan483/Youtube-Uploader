import config
from utils.logging import LoggerMixin


class QuotaStateStore(LoggerMixin):
    def __init__(self, json_store, logger=None):
        self.json_store = json_store
        self.logger = logger

    def load(self):
        return self.json_store.load_json_with_validation(
            config.QUOTA_STATE_FILE,
            self._validate_schema
        )

    def save(self, data):
        self.json_store.atomic_write_json(config.QUOTA_STATE_FILE, data)

    def _validate_schema(self, data):
        if not isinstance(data, dict):
            return False
        if not data:
            return True
        if 'last_quota_hit' in data:
            if isinstance(data['last_quota_hit'], str):
                return True
        self._log("Invalid quota_state schema")
        return False
