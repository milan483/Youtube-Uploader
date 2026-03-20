import hashlib
import os
import shutil
from pathlib import Path
from typing import Optional, Tuple
import config
from utils.logging import LoggerMixin
from utils.config_utils import is_supported_video_file, format_file_size


class FileOperationError(Exception):
    pass


class FileHandler(LoggerMixin):
    def __init__(self, logger=None):
        self.logger = logger

    def set_logger(self, logger):
        self.logger = logger

    def validate_path(self, filepath, base_dir=None):
        try:
            if '\0' in filepath:
                self._log(f"Path validation failed: null byte in path: {filepath}")
                return False
            
            abs_path = Path(filepath).resolve()
            
            if base_dir:
                base_path = Path(base_dir).resolve()
                try:
                    abs_path.relative_to(base_path)
                except ValueError:
                    self._log(f"Path validation failed: {filepath} is outside {base_dir}")
                    return False
            
            return True
            
        except Exception as e:
            self._log(f"Error validating path {filepath}: {str(e)}")
            return False

    def compute_file_hash(self, filepath):
        try:
            if not os.path.isfile(filepath):
                self._log(f"Cannot hash: {filepath} is not a file")
                return None

            file_size = os.path.getsize(filepath)
            filename = os.path.basename(filepath)
            size_str = format_file_size(file_size)

            self._log(f"Hashing {filename} ({size_str})...")

            hasher = hashlib.md5()
            bytes_read = 0
            last_logged_percent = 0

            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(config.MD5_CHUNK_SIZE)
                    if not chunk:
                        break
                    hasher.update(chunk)

                    bytes_read += len(chunk)
                    if file_size > 0:
                        current_percent = int((bytes_read / file_size) * 100)
                        if current_percent >= last_logged_percent + 10:
                            last_logged_percent = (current_percent // 10) * 10
                            read_str = format_file_size(bytes_read)
                            self._log(f"Hashing {filename}: {last_logged_percent}% ({read_str} / {size_str})")

            hash_value = hasher.hexdigest()
            self._log(f"Hash complete for {filename}: {hash_value}")
            return hash_value
            
        except PermissionError:
            self._log(f"Permission denied reading file: {filepath}")
            return None
        except IOError as e:
            self._log(f"I/O error reading file {filepath}: {str(e)}")
            return None
        except Exception as e:
            self._log(f"Unexpected error computing hash for {filepath}: {str(e)}")
            return None

    def verify_copy(self, source_path, destination_path, cached_source_hash=None):
        try:
            if cached_source_hash:
                source_hash = cached_source_hash
                self._log(f"Using cached hash for {os.path.basename(source_path)}: {source_hash}")
            else:
                source_hash = self.compute_file_hash(source_path)
                if source_hash is None:
                    self._log(f"Failed to hash source file: {source_path}")
                    return False

            dest_hash = self.compute_file_hash(destination_path)
            if dest_hash is None:
                self._log(f"Failed to hash destination file: {destination_path}")
                return False

            if source_hash == dest_hash:
                self._log(f"Copy verification successful: {os.path.basename(source_path)}")
                return True
            else:
                self._log(f"Copy verification FAILED: {os.path.basename(source_path)} "
                         f"(source: {source_hash}, dest: {dest_hash})")
                return False

        except Exception as e:
            self._log(f"Error during copy verification: {str(e)}")
            return False

    def safe_copy_and_verify(self, source_path, destination_path, cached_source_hash=None):
        try:
            if not os.path.isfile(source_path):
                self._log(f"Source file does not exist: {source_path}")
                return False

            dest_dir = os.path.dirname(destination_path)
            if dest_dir and not os.path.exists(dest_dir):
                self._log(f"Destination directory does not exist: {dest_dir}")
                return False

            filename = os.path.basename(source_path)
            file_size = os.path.getsize(source_path)
            size_str = format_file_size(file_size)

            self._log(f"Copying {filename} ({size_str})...")

            bytes_copied = 0
            last_logged_percent = 0

            with open(source_path, 'rb') as src, open(destination_path, 'wb') as dst:
                while True:
                    chunk = src.read(config.COPY_CHUNK_SIZE)
                    if not chunk:
                        break
                    dst.write(chunk)

                    bytes_copied += len(chunk)
                    if file_size > 0:
                        current_percent = int((bytes_copied / file_size) * 100)
                        if current_percent >= last_logged_percent + 10:
                            last_logged_percent = (current_percent // 10) * 10
                            copied_str = format_file_size(bytes_copied)
                            self._log(f"Copying {filename}: {last_logged_percent}% ({copied_str} / {size_str})")

            shutil.copystat(source_path, destination_path)
            self._log(f"Copy complete for {filename}")

            if self.verify_copy(source_path, destination_path, cached_source_hash):
                self._log(f"Successfully copied and verified: {os.path.basename(source_path)}")
                return True
            else:
                self._log(f"Copy verification failed for: {os.path.basename(source_path)}")
                try:
                    if os.path.exists(destination_path):
                        os.remove(destination_path)
                        self._log(f"Cleaned up failed copy: {destination_path}")
                except Exception as cleanup_error:
                    self._log(f"Warning: Could not clean up failed copy: {cleanup_error}")
                return False

        except PermissionError:
            self._log(f"Permission denied copying {source_path} to {destination_path}")
            return False
        except IOError as e:
            self._log(f"I/O error copying file: {str(e)}")
            return False
        except Exception as e:
            self._log(f"Unexpected error copying file: {str(e)}")
            return False

    def _are_on_same_drive(self, path1, path2):
        try:
            abs1 = os.path.abspath(path1)
            abs2 = os.path.abspath(path2)

            if os.name == 'nt':
                drive1 = os.path.splitdrive(abs1)[0].upper()
                drive2 = os.path.splitdrive(abs2)[0].upper()
                return drive1 == drive2
            else:
                stat1 = os.stat(abs1)
                parent2 = os.path.dirname(abs2)
                stat2 = os.stat(parent2) if os.path.exists(parent2) else os.stat(abs2)
                return stat1.st_dev == stat2.st_dev
        except Exception:
            return False

    def safe_move(self, source_path, destination_path, cached_source_hash=None):
        import time
        try:
            if os.path.exists(destination_path):
                dest_dir = os.path.dirname(destination_path)
                dest_filename = os.path.basename(destination_path)
                name_without_ext, ext = os.path.splitext(dest_filename)
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                new_filename = f"{name_without_ext}_{timestamp}{ext}"
                destination_path = os.path.join(dest_dir, new_filename)
                self._log(f"Destination file exists; using {new_filename} instead")

            dest_dir = os.path.dirname(destination_path)
            if dest_dir and not os.path.exists(dest_dir):
                try:
                    os.makedirs(dest_dir, exist_ok=True)
                except Exception as e:
                    return False, f"Could not create destination directory: {e}"

            same_drive = self._are_on_same_drive(source_path, destination_path)

            if same_drive:
                try:
                    os.rename(source_path, destination_path)
                    msg = f"Successfully moved {os.path.basename(source_path)}"
                    self._log(msg)
                    return True, msg
                except OSError as e:
                    self._log(f"Fast move failed ({e}), falling back to copy+verify...")
                    same_drive = False

            if not same_drive:
                if not self.safe_copy_and_verify(source_path, destination_path, cached_source_hash):
                    return False, "Copy or verification failed"

                last_error = None
                delay = config.INITIAL_FILE_OPERATION_DELAY
                for attempt in range(config.MAX_FILE_OPERATION_RETRIES):
                    try:
                        if attempt > 0:
                            delay = min(
                                config.INITIAL_FILE_OPERATION_DELAY * (2 ** attempt),
                                config.MAX_FILE_OPERATION_DELAY
                            )
                        if delay > 0:
                            time.sleep(delay)

                        os.remove(source_path)
                        msg = f"Successfully moved {os.path.basename(source_path)}"
                        if attempt > 0:
                            msg += f" (after {attempt + 1} attempts)"
                        self._log(msg)
                        return True, msg

                    except PermissionError as e:
                        last_error = e
                        if attempt < config.MAX_FILE_OPERATION_RETRIES - 1:
                            self._log(f"File locked (attempt {attempt + 1}/{config.MAX_FILE_OPERATION_RETRIES}), "
                                    f"retrying in {delay:.1f}s...")
                    except Exception as e:
                        last_error = e
                        if attempt < config.MAX_FILE_OPERATION_RETRIES - 1:
                            self._log(f"Error deleting file (attempt {attempt + 1}/{config.MAX_FILE_OPERATION_RETRIES}): {str(e)}, "
                                    f"retrying in {delay:.1f}s...")

                msg = f"Could not delete original file: {str(last_error)}"
                self._log(msg)
                return False, msg

        except Exception as e:
            msg = f"Error during safe move: {str(e)}"
            self._log(msg)
            return False, msg

    def ensure_directory_exists(self, directory_path):
        try:
            os.makedirs(directory_path, exist_ok=True)
            return True
        except PermissionError:
            self._log(f"Permission denied creating directory: {directory_path}")
            return False
        except Exception as e:
            self._log(f"Error creating directory {directory_path}: {str(e)}")
            return False

    def get_video_files(self, directory_path):
        try:
            if not os.path.isdir(directory_path):
                self._log(f"Not a directory: {directory_path}")
                return []
            
            all_files = os.listdir(directory_path)
            
            video_files = [
                f for f in all_files
                if is_supported_video_file(f) and
                   os.path.isfile(os.path.join(directory_path, f))
            ]
            
            video_files.sort()
            
            self._log(f"Found {len(video_files)} video file(s) in {directory_path}")
            return video_files
            
        except PermissionError:
            self._log(f"Permission denied accessing directory: {directory_path}")
            return []
        except Exception as e:
            self._log(f"Error listing video files in {directory_path}: {str(e)}")
            return []

    def get_file_size_mb(self, filepath):
        try:
            size_bytes = os.path.getsize(filepath)
            size_mb = size_bytes / (1024 * 1024)
            return size_mb
        except Exception as e:
            self._log(f"Error getting file size for {filepath}: {str(e)}")
            return 0
