"""Safe enumeration and recycling of local archived video clips.

All operations are confined to the selected watch root's central Uploaded folder.
Remote YouTube content and upload history are intentionally untouched.
"""
import ntpath
import os
from dataclasses import dataclass
from pathlib import Path

from file_handler import FileHandler
from utils.config_utils import get_uploaded_folder_path, is_supported_video_file


@dataclass(frozen=True)
class ArchivedClip:
    relative_path: str
    size_bytes: int


@dataclass(frozen=True)
class DeleteResult:
    deleted: tuple
    failed: dict


def _system_trash(path):
    # Lazy import permits read-only browsing when optional dependency is absent.
    from send2trash import send2trash
    send2trash(path)


class UploadedClipsManager:
    """Filesystem-only archive manager; never touches YouTube or state files."""

    def __init__(self, file_handler, trash_func=None):
        self.file_handler = file_handler
        self._trash = trash_func or _system_trash

    @staticmethod
    def _no_link_components(path):
        """Reject links/junctions in the complete existing path, including parents."""
        absolute = Path(os.path.abspath(path))
        current = Path(absolute.anchor)
        for part in absolute.parts[1:]:
            current = current / part
            if FileHandler._is_link_or_junction(current):
                return False
        return True

    def _archive_root(self, watch_root):
        if not watch_root or not isinstance(watch_root, (str, os.PathLike)):
            raise ValueError("Select a valid watch folder")
        root = os.path.abspath(os.fspath(watch_root))
        if not os.path.isdir(root) or not self._no_link_components(root):
            raise ValueError("Watch folder is unavailable or contains a symlink/junction")
        archive = os.path.abspath(get_uploaded_folder_path(root))
        if os.path.commonpath((root, archive)) != root:
            raise ValueError("Invalid Uploaded archive location")
        if not self._no_link_components(archive):
            raise ValueError("Uploaded archive contains a symlink/junction")
        return archive

    @staticmethod
    def _validate_relative_name(name):
        if not isinstance(name, str) or not name or '\x00' in name:
            raise ValueError("Invalid clip name")
        if (os.path.isabs(name) or ntpath.isabs(name) or ntpath.splitdrive(name)[0]
                or ('\\' in name and os.sep != '\\')):
            raise ValueError("Absolute or foreign-platform clip path")
        parts = Path(name).parts
        if (not parts or any(part in ("", ".", "..") or part.startswith(".") for part in parts)
                or not is_supported_video_file(parts[-1])):
            raise ValueError("Invalid clip path")
        return name

    def _clip_path(self, archive, relative_name):
        self._validate_relative_name(relative_name)
        candidate = os.path.abspath(os.path.join(archive, relative_name))
        try:
            if os.path.commonpath((archive, candidate)) != archive or candidate == archive:
                raise ValueError("Clip is outside the Uploaded archive")
        except ValueError:
            raise ValueError("Clip is outside the Uploaded archive")
        if not self._no_link_components(candidate):
            raise ValueError("Clip uses a symlink/junction")
        if not os.path.isfile(candidate):
            raise ValueError("Clip no longer exists or is not a regular file")
        return candidate

    def list_clips(self, watch_root):
        """Return a sorted snapshot of supported, completed archive clips."""
        with self.file_handler.archive_lock:
            archive = self._archive_root(watch_root)
            if not os.path.isdir(archive):
                return []
            clips = []
            for current, dirs, files in os.walk(archive, topdown=True, followlinks=False):
                dirs[:] = [
                    d for d in dirs
                    if not d.startswith(".")
                    and not FileHandler._is_link_or_junction(os.path.join(current, d))
                ]
                for name in files:
                    if name.startswith(".") or not is_supported_video_file(name):
                        continue
                    path = os.path.join(current, name)
                    relative = os.path.relpath(path, archive)
                    try:
                        checked_path = self._clip_path(archive, relative)
                        clips.append(ArchivedClip(relative, os.path.getsize(checked_path)))
                    except (OSError, ValueError):
                        continue
            return sorted(clips, key=lambda clip: clip.relative_path.casefold())

    def delete_clips(self, watch_root, relative_names):
        """Recycle selected archived clips, validating each name at operation time.

        Callers handle user confirmation. Failure never falls back to permanent
        deletion; each failed item is returned with a human-readable error.
        """
        deleted = []
        failed = {}
        with self.file_handler.archive_lock:
            try:
                archive = self._archive_root(watch_root)
            except (OSError, ValueError) as error:
                return DeleteResult((), {name: str(error) for name in relative_names})
            for relative_name in dict.fromkeys(relative_names):
                try:
                    filepath = self._clip_path(archive, relative_name)
                    self._trash(filepath)
                    deleted.append(relative_name)
                except Exception as error:
                    failed[relative_name] = str(error)
        return DeleteResult(tuple(deleted), failed)
