import config
from utils.logging import LoggerMixin


class PlaylistSortStore(LoggerMixin):
    def __init__(self, json_store, logger=None):
        self.json_store = json_store
        self.logger = logger

    def load(self):
        return self.json_store.load_json_with_validation(
            config.PLAYLIST_SORT_STATE_FILE,
            self._validate_schema
        )

    def save(self, data):
        self.json_store.atomic_write_json(config.PLAYLIST_SORT_STATE_FILE, data)

    def _validate_schema(self, data):
        if not isinstance(data, dict):
            return False
        if not data:
            return True

        required_keys = ['playlist_id', 'sorted_items', 'last_position']
        if not all(key in data for key in required_keys):
            self._log("Invalid playlist_sort_state schema: missing keys")
            return False

        if not isinstance(data['sorted_items'], list):
            self._log("Invalid playlist_sort_state schema: sorted_items not a list")
            return False

        if not isinstance(data['last_position'], int):
            self._log("Invalid playlist_sort_state schema: last_position not an int")
            return False

        return True
