import hashlib
import os
import shutil
import stat
import threading
import tempfile
from pathlib import Path
from typing import Optional, Tuple
import config
from utils.logging import LoggerMixin
from utils.config_utils import is_supported_video_file, format_file_size


def move_to_system_trash(path):
    # Keep the dependency lazy so ordinary uploads and archive browsing still work.
    from send2trash import send2trash
    send2trash(path)


class FileOperationError(Exception):
    pass


class FileHandler(LoggerMixin):
    def __init__(self, logger=None):
        self.logger = logger
        # Shared by archiving and local Trash operations in this process.
        self.archive_lock = threading.RLock()

    def set_logger(self, logger):
        self.logger = logger

    @staticmethod
    def _is_link_or_junction(path):
        try:
            if os.path.islink(path):
                return True
            is_junction = getattr(os.path, "isjunction", None)
            if is_junction and is_junction(path):
                return True
            attributes = os.lstat(path).st_file_attributes
            return bool(attributes & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT
        except (OSError, AttributeError):
            return False

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

    def _unique_destination_path(self, destination_path):
        """Return an unused collision name; publication still must be exclusive."""
        dest_dir = os.path.dirname(destination_path)
        filename = os.path.basename(destination_path)
        name, ext = os.path.splitext(filename)
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        candidate = os.path.join(dest_dir, f"{name}_{timestamp}{ext}")
        index = 1
        while os.path.lexists(candidate):
            candidate = os.path.join(dest_dir, f"{name}_{timestamp}_{index}{ext}")
            index += 1
        return candidate

    def _publish_without_overwrite(self, staged_path, destination_path):
        """Atomically publish a same-filesystem staging file without replacing a target."""
        try:
            os.link(staged_path, destination_path)
        except FileExistsError:
            return False
        return True

    def safe_move(self, source_path, destination_path, cached_source_hash=None):
        # Do not expose partly-published archives to the manager while moving.
        with self.archive_lock:
            return self._safe_move_unlocked(source_path, destination_path, cached_source_hash)

    def _safe_move_unlocked(self, source_path, destination_path, cached_source_hash=None):
        import time
        try:
            if not os.path.isfile(source_path) or self._is_link_or_junction(source_path):
                return False, "Source is not a regular non-symlink file"

            dest_dir = os.path.dirname(destination_path)
            if dest_dir and not os.path.exists(dest_dir):
                try:
                    os.makedirs(dest_dir, exist_ok=True)
                except Exception as e:
                    return False, f"Could not create destination directory: {e}"

            original_destination = destination_path
            index = 0
            while True:
                candidate = original_destination if index == 0 else self._unique_destination_path(original_destination)
                index += 1
                # lexists also detects dangling symlinks. Never write through or replace one.
                if os.path.lexists(candidate):
                    continue

                try:
                    same_drive = self._are_on_same_drive(source_path, candidate)
                    if same_drive:
                        if os.name == "nt":
                            # Windows rename is atomic and refuses an existing target.
                            try:
                                os.rename(source_path, candidate)
                                msg = f"Successfully moved {os.path.basename(source_path)}"
                                self._log(msg)
                                return True, msg
                            except FileExistsError:
                                continue
                        # Hard-link publication is atomic and fails if another process wins
                        # the name between the existence check and publication.
                        if self._publish_without_overwrite(source_path, candidate):
                            published_destination = candidate
                            break
                        continue
                except FileExistsError:
                    continue
                except OSError as e:
                    self._log(f"Fast move failed ({e}), falling back to staged copy...")

                # Cross-volume copies are written under a hidden, non-video suffix and
                # verified before atomic no-clobber publication.
                stage_fd, staged_path = tempfile.mkstemp(
                    prefix=".upload-staging-", suffix=".part", dir=dest_dir or "."
                )
                os.close(stage_fd)
                try:
                    if not self.safe_copy_and_verify(source_path, staged_path, cached_source_hash):
                        return False, "Copy or verification failed"
                    if os.name == "nt":
                        try:
                            os.rename(staged_path, candidate)
                            published = True
                        except FileExistsError:
                            published = False
                    else:
                        try:
                            published = self._publish_without_overwrite(staged_path, candidate)
                        except FileExistsError:
                            published = False
                    if not published:
                        continue
                    published_destination = candidate
                    # The verified destination is complete before the source is removed.
                    break
                finally:
                    try:
                        if os.path.lexists(staged_path):
                            os.remove(staged_path)
                    except OSError as cleanup_error:
                        self._log(f"Warning: Could not clean up staging file {staged_path}: {cleanup_error}")

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
            try:
                if os.path.lexists(published_destination):
                    os.remove(published_destination)
            except OSError as cleanup_error:
                self._log(f"Could not remove published duplicate {published_destination}: {cleanup_error}")
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

    @staticmethod
    def is_safe_watch_file(filepath, watch_root):
        """Validate a regular file inside a watch tree without symlink paths."""
        try:
            raw_file = os.fspath(filepath)
            raw_root = os.fspath(watch_root)
            if ".." in Path(raw_file).parts or ".." in Path(raw_root).parts:
                return False

            def normalize_without_symlinks(raw_path):
                path = Path(raw_path)
                if not path.is_absolute():
                    path = Path.cwd() / path
                current = Path(path.anchor)
                for part in path.parts[1:]:
                    if part in ("", "."):
                        continue
                    if part == "..":
                        if FileHandler._is_link_or_junction(current):
                            raise ValueError("symlink path component")
                        current = current.parent
                        continue
                    current /= part
                    if FileHandler._is_link_or_junction(current):
                        raise ValueError("symlink path component")
                return current

            file_path = normalize_without_symlinks(raw_file)
            root_path = normalize_without_symlinks(raw_root)
            if not root_path.is_dir():
                return False
            relative = file_path.relative_to(root_path)
            if not relative.parts or any(
                part.startswith(".") or part.casefold() == "uploaded"
                for part in relative.parts
            ):
                return False

            current = root_path
            for part in relative.parts:
                current = current / part
                if FileHandler._is_link_or_junction(current):
                    return False
            if not file_path.is_file():
                return False
            # Resolve as a final guard against path traversal and platform oddities.
            file_path.resolve(strict=True).relative_to(root_path.resolve(strict=True))
            return True
        except (OSError, ValueError, TypeError):
            return False

    def trash_source_signature(self, filepath, watch_root=None):
        """Return a signature only for a regular source outside archive/link paths."""
        path = Path(filepath)
        if any(part == ".." or part.casefold() == "uploaded" for part in path.parts):
            return None
        try:
            if watch_root is not None:
                if not self.is_safe_watch_file(path, watch_root):
                    return None
            elif any(self._is_link_or_junction(part) for part in (*path.parents, path)):
                return None
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode):
                return None
            return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        except OSError:
            return None

    def trash_uploaded_source(self, filepath, file_hash, signature, watch_root=None):
        """Recycle only the unchanged source verified before upload."""
        with self.archive_lock:
            if signature is None or self.trash_source_signature(filepath, watch_root) != signature:
                raise FileOperationError("Source path is unsafe, unavailable, or changed during upload")
            if (self.compute_file_hash(filepath) != file_hash
                    or self.trash_source_signature(filepath, watch_root) != signature):
                raise FileOperationError("Could not verify that the source is unchanged")
            move_to_system_trash(os.fspath(filepath))

    def get_video_files(self, directory_path, recursive=False):
        try:
            root = Path(os.path.abspath(directory_path))
            if not root.is_dir() or self._is_link_or_junction(root):
                self._log(f"Not a directory: {directory_path}")
                return []
            root_component = Path(root.anchor)
            for component in root.parts[1:]:
                root_component /= component
                if self._is_link_or_junction(root_component):
                    self._log(f"Watch directory has a symlink ancestor: {root_component}")
                    return []

            video_files = []

            def scan(directory):
                try:
                    entries = list(os.scandir(directory))
                except PermissionError:
                    self._log(f"Permission denied accessing directory: {directory}")
                    return
                except OSError as error:
                    self._log(f"Could not access directory {directory}: {error}")
                    return

                for entry in entries:
                    name = entry.name
                    if name.startswith(".") or name.casefold() == "uploaded":
                        continue
                    try:
                        if self._is_link_or_junction(entry.path):
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            if recursive:
                                scan(entry.path)
                        elif entry.is_file(follow_symlinks=False) and is_supported_video_file(name):
                            relpath = os.path.relpath(entry.path, root)
                            video_files.append(relpath)
                    except OSError as error:
                        self._log(f"Could not inspect {entry.path}: {error}")

            scan(str(root))
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
