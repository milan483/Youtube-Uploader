import json
import os
import time
import tempfile
import shutil
from utils.logging import LoggerMixin


class JsonStore(LoggerMixin):
    def __init__(self, logger=None, error_cls=Exception):
        self.logger = logger
        self.error_cls = error_cls

    def atomic_write_json(self, filepath, data):
        try:
            directory = os.path.dirname(filepath) or '.'
            os.makedirs(directory, mode=0o700, exist_ok=True)

            with tempfile.NamedTemporaryFile(
                mode='w',
                dir=directory,
                delete=False,
                suffix='.tmp'
            ) as tmp_file:
                json.dump(data, tmp_file, indent=2)
                temp_path = tmp_file.name
                tmp_file.flush()
                os.fsync(tmp_file.fileno())

            if os.path.exists(filepath):
                os.replace(temp_path, filepath)
            else:
                os.rename(temp_path, filepath)

            self._log(f"Atomically wrote {os.path.basename(filepath)}")

        except Exception as e:
            try:
                if 'temp_path' in locals() and os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass

            error_msg = f"Failed to write {filepath}: {str(e)}"
            self._log(error_msg)
            raise self.error_cls(error_msg)

    def load_json_with_validation(self, filepath, schema_validator=None):
        if not os.path.exists(filepath):
            self._log(f"{os.path.basename(filepath)} does not exist (first run?)")
            return {}

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            if schema_validator:
                if not schema_validator(data):
                    raise ValueError("Schema validation failed")

            self._log(f"Successfully loaded {os.path.basename(filepath)}")
            return data

        except json.JSONDecodeError as e:
            backup_path = f"{filepath}.corrupt.{int(time.time())}"
            self._log(f"WARNING: {filepath} is corrupted (JSON decode error)")
            self._log(f"Creating backup: {backup_path}")

            try:
                os.replace(filepath, backup_path)
                self._log(f"Moved corrupted file to {backup_path}")
            except Exception as backup_error:
                self._log(f"Could not move corrupted file: {backup_error}")
                try:
                    shutil.copy2(filepath, backup_path)
                    os.remove(filepath)
                except Exception as copy_error:
                    self._log(f"Could not create backup: {copy_error}")

            return {}

        except Exception as e:
            self._log(f"Error loading {filepath}: {str(e)}")
            return {}
