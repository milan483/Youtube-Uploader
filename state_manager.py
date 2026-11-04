import os
from datetime import datetime
import shutil
import config
from utils.logging import LoggerMixin
from storage.json_store import JsonStore
from storage.upload_history_store import UploadHistoryStore
from storage.upload_state_store import UploadStateStore
from storage.quota_state_store import QuotaStateStore
from storage.playlist_sort_store import PlaylistSortStore
from storage.preferences_store import PreferencesStore


class StateManagerError(Exception):
    pass


class StateManager(LoggerMixin):
    def __init__(self, logger=None):
        self.logger = logger
        self.json_store = JsonStore(self.logger, StateManagerError)
        self.upload_history_store = UploadHistoryStore(self.json_store, self.logger)
        self.upload_state_store = UploadStateStore(self.json_store, self.logger)
        self.quota_state_store = QuotaStateStore(self.json_store, self.logger)
        self.playlist_sort_store = PlaylistSortStore(self.json_store, self.logger)
        self.preferences_store = PreferencesStore(self.json_store, self.logger)

        self.upload_history = {}
        self.upload_states = {}
        self.quota_state = {}
        self.playlist_sort_state = {}

        self._load_all_state()

    def _load_all_state(self):
        self.upload_history = self.upload_history_store.load()
        self.upload_states = self.upload_state_store.load()
        self.quota_state = self.quota_state_store.load()
        self.playlist_sort_state = self.playlist_sort_store.load()
        self.user_preferences = self.preferences_store.load()
        self._log("State loading complete")

    def is_file_uploaded(self, file_hash):
        return file_hash in self.upload_history

    def add_upload_to_history(self, file_hash, filename, video_id):
        self.upload_history[file_hash] = {
            'filename': filename,
            'upload_date': datetime.now().isoformat(),
            'video_id': video_id
        }
        self.upload_history_store.save(self.upload_history)
        self._log(f"Added {filename} to upload history")

    def get_upload_count(self):
        return len(self.upload_history)

    def set_upload_state(self, filepath, state, retry_count=None, next_retry_time=None):
        state_info = {
            'state': state,
            'timestamp': datetime.now().isoformat()
        }
        if retry_count is not None:
            state_info['retry_count'] = retry_count
        if next_retry_time is not None:
            state_info['next_retry_time'] = next_retry_time

        self.upload_states[filepath] = state_info
        self.upload_state_store.save(self.upload_states)
        self._log(f"Set upload state for {os.path.basename(filepath)}: {state}")

    def get_upload_state(self, filepath):
        if filepath in self.upload_states:
            return self.upload_states[filepath].get('state')
        return None

    def get_incomplete_uploads(self):
        incomplete = []
        for filepath, state_info in self.upload_states.items():
            if state_info['state'] == 'uploading':
                if os.path.exists(filepath):
                    incomplete.append(filepath)
                    self._log(f"Found incomplete upload: {os.path.basename(filepath)}")
        return incomplete

    def reset_incomplete_uploads_to_pending(self):
        count = 0
        for filepath, state_info in list(self.upload_states.items()):
            if state_info['state'] == 'uploading' and os.path.exists(filepath):
                self.set_upload_state(filepath, 'pending')
                count += 1
        if count > 0:
            self._log(f"Reset {count} incomplete upload(s) to pending")
        return count

    def get_retry_count(self, filepath):
        if filepath in self.upload_states:
            return self.upload_states[filepath].get('retry_count', 0)
        return 0

    def get_retry_info(self, filepath):
        if filepath not in self.upload_states:
            return {'state': None, 'retry_count': 0, 'next_retry_time': None}
        state_info = self.upload_states[filepath]
        return {
            'state': state_info.get('state'),
            'retry_count': state_info.get('retry_count', 0),
            'next_retry_time': state_info.get('next_retry_time')
        }

    def is_ready_for_retry(self, filepath):
        if filepath not in self.upload_states:
            return False

        state_info = self.upload_states[filepath]

        if state_info.get('state') != 'failed':
            return False

        retry_count = state_info.get('retry_count', 0)
        if retry_count >= config.MAX_UPLOAD_RETRY_ATTEMPTS:
            return False

        next_retry_time = state_info.get('next_retry_time')
        if next_retry_time:
            try:
                next_retry_dt = datetime.fromisoformat(next_retry_time)
                if datetime.now() < next_retry_dt:
                    return False
            except Exception:
                pass

        return True

    def get_failed_uploads_for_retry(self):
        retry_list = []
        for filepath, state_info in self.upload_states.items():
            if self.is_ready_for_retry(filepath) and os.path.exists(filepath):
                retry_list.append(filepath)
                self._log(f"File ready for retry: {os.path.basename(filepath)} "
                         f"(attempt {state_info.get('retry_count', 0) + 1}/{config.MAX_UPLOAD_RETRY_ATTEMPTS})")
        return retry_list

    def get_last_quota_hit(self):
        return self.quota_state.get('last_quota_hit')

    def record_quota_hit(self):
        now = datetime.now().isoformat()
        self.quota_state['last_quota_hit'] = now
        self.quota_state_store.save(self.quota_state)
        self._log(f"Recorded quota hit at {now}")

    def clear_quota_state(self):
        self.quota_state = {}
        self.quota_state_store.save(self.quota_state)
        self._log("Cleared quota state")

    def get_playlist_sort_state(self, playlist_id):
        if not self.playlist_sort_state:
            return None
        if self.playlist_sort_state.get('playlist_id') == playlist_id:
            return self.playlist_sort_state
        else:
            return None

    def save_playlist_sort_state(self, playlist_id, sorted_items, last_position):
        self.playlist_sort_state = {
            'playlist_id': playlist_id,
            'sorted_items': sorted_items,
            'last_position': last_position
        }
        self.playlist_sort_store.save(self.playlist_sort_state)
        self._log(f"Saved playlist sort state at position {last_position}")

    def clear_playlist_sort_state(self):
        self.playlist_sort_state = {}
        self.playlist_sort_store.save(self.playlist_sort_state)
        self._log("Cleared playlist sort state")

    def get_statistics(self):
        stats = {
            'total_uploads': len(self.upload_history),
            'pending_uploads': sum(1 for s in self.upload_states.values() if s['state'] == 'pending'),
            'uploading_now': sum(1 for s in self.upload_states.values() if s['state'] == 'uploading'),
            'completed_uploads': sum(1 for s in self.upload_states.values() if s['state'] == 'completed'),
            'failed_uploads': sum(1 for s in self.upload_states.values() if s['state'] == 'failed'),
            'in_quota_cooldown': bool(self.get_last_quota_hit())
        }
        return stats

    def export_state_for_backup(self, backup_dir):
        try:
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            files_to_backup = [
                config.UPLOAD_HISTORY_FILE,
                config.UPLOAD_STATE_FILE,
                config.QUOTA_STATE_FILE,
                config.PLAYLIST_SORT_STATE_FILE
            ]

            for filename in files_to_backup:
                if os.path.exists(filename):
                    backup_name = f"{filename}.{timestamp}.backup"
                    backup_path = os.path.join(backup_dir, backup_name)
                    shutil.copy2(filename, backup_path)
                    self._log(f"Backed up {filename} to {backup_path}")

            return True
        except Exception as e:
            self._log(f"Error creating backup: {str(e)}")
            return False

    def get_preference(self, key, default=None):
        return self.user_preferences.get(key, default)

    def set_preference(self, key, value):
        self.user_preferences[key] = value
        self.preferences_store.save(self.user_preferences)
        self._log(f"Saved preference: {key}")

    def get_all_preferences(self):
        defaults = {
            'last_watch_folder': '',
            'scan_subdirectories': False,
            'privacy_setting': config.DEFAULT_PRIVACY_SETTING,
            'playlist_title': 'No Playlist',
            'video_category': config.DEFAULT_VIDEO_CATEGORY,
            'autonomous_mode': config.DEFAULT_AUTONOMOUS_MODE,
            'auto_start_watching': config.DEFAULT_AUTO_START_WATCHING,
            'start_minimized': config.DEFAULT_START_MINIMIZED,
            'notify_when_empty': config.DEFAULT_NOTIFY_WHEN_EMPTY,
            'auto_close_when_empty': config.DEFAULT_AUTO_CLOSE_WHEN_EMPTY,
            'start_with_windows': False,
            'notify_upload_success': config.DEFAULT_NOTIFY_UPLOAD_SUCCESS,
            'notify_upload_failed': config.DEFAULT_NOTIFY_UPLOAD_FAILED,
            'notify_quota_exceeded': config.DEFAULT_NOTIFY_QUOTA_EXCEEDED,
            'notify_batch_complete': config.DEFAULT_NOTIFY_BATCH_COMPLETE
        }
        prefs = defaults.copy()
        prefs.update(self.user_preferences)
        return prefs

    def save_all_preferences(self, preferences):
        self.user_preferences = preferences
        self.preferences_store.save(self.user_preferences)
        self._log("Saved all user preferences")
