import hashlib
import os
from pathlib import Path

import pytest

from file_handler import FileHandler


def write_binary_file(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def test_compute_file_hash_matches_md5(tmp_path):
    path = tmp_path / "clip.mp4"
    data = b"sample-video-bytes"
    write_binary_file(path, data)

    digest = FileHandler().compute_file_hash(str(path))
    assert digest == hashlib.md5(data).hexdigest()


def test_safe_move_moves_file_and_cleans_source(tmp_path):
    source_file = tmp_path / "source" / "video.mp4"
    destination_file = tmp_path / "uploaded" / "video.mp4"
    write_binary_file(source_file, b"content")
    destination_file.parent.mkdir(parents=True, exist_ok=True)

    success, message = FileHandler().safe_move(str(source_file), str(destination_file))

    assert success
    assert "Successfully moved" in message
    assert destination_file.exists()
    assert not source_file.exists()


def test_validate_path_rejects_outside_base_dir(tmp_path):
    base = tmp_path / "watch"
    base.mkdir(parents=True, exist_ok=True)
    outside_file = tmp_path / "other" / "clip.mp4"

    assert not FileHandler().validate_path(str(outside_file), base_dir=str(base))


def test_get_video_files_is_top_level_by_default_and_recursive_when_requested(tmp_path):
    root = tmp_path / "watch"
    write_binary_file(root / "z.mp4", b"z")
    write_binary_file(root / "Game" / "clip.mov", b"mov")
    write_binary_file(root / "Game" / "deep" / "clip.mp4", b"mp4")
    write_binary_file(root / "a.txt", b"text")

    handler = FileHandler()
    assert handler.get_video_files(str(root)) == ["z.mp4"]
    assert handler.get_video_files(str(root), recursive=True) == [
        os.path.join("Game", "clip.mov"),
        os.path.join("Game", "deep", "clip.mp4"),
        "z.mp4",
    ]


def test_get_video_files_excludes_hidden_uploaded_and_symlink_trees(tmp_path):
    root = tmp_path / "watch"
    write_binary_file(root / "clip.mp4", b"clip")
    write_binary_file(root / "Uploaded" / "old.mp4", b"old")
    write_binary_file(root / "game" / "uPLOADed" / "legacy.mp4", b"legacy")
    write_binary_file(root / ".staging" / "temp.mp4", b"temp")
    outside = tmp_path / "outside"
    write_binary_file(outside / "outside.mp4", b"outside")
    try:
        (root / "linked").symlink_to(outside, target_is_directory=True)
        (root / "loop").symlink_to(root, target_is_directory=True)
        (root / "linked-file.mp4").symlink_to(outside / "outside.mp4")
    except (OSError, NotImplementedError):
        pass

    assert FileHandler().get_video_files(str(root), recursive=True) == ["clip.mp4"]


def test_get_video_files_skips_unreadable_subtree(tmp_path, monkeypatch):
    root = tmp_path / "watch"
    write_binary_file(root / "ok.mp4", b"ok")
    write_binary_file(root / "denied" / "hidden.mp4", b"hidden")
    real_scandir = os.scandir

    def scandir(path):
        if os.fspath(path) == str(root / "denied"):
            raise PermissionError("denied")
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", scandir)
    assert FileHandler().get_video_files(str(root), recursive=True) == ["ok.mp4"]


def test_is_safe_watch_file_requires_contained_regular_non_symlink_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "watch"
    inside = root / "Game" / "clip.mp4"
    write_binary_file(inside, b"inside")
    outside = tmp_path / "outside.mp4"
    write_binary_file(outside, b"outside")
    (root / "Uploaded").mkdir()
    write_binary_file(root / "Uploaded" / "archived.mp4", b"archived")
    (root / ".hidden").mkdir()
    write_binary_file(root / ".hidden" / "hidden.mp4", b"hidden")

    safe = FileHandler.is_safe_watch_file
    assert safe(str(inside), str(root))
    assert not safe(str(outside), str(root))
    assert not safe(str(root / "Uploaded" / "archived.mp4"), str(root))
    assert not safe(str(root / ".hidden" / "hidden.mp4"), str(root))
    assert safe(os.path.join("watch", "Game", "clip.mp4"), "watch")
    assert not safe(os.path.join("watch", "Game", "..", "Game", "clip.mp4"), "watch")

    try:
        (root / "escape.mp4").symlink_to(outside)
        assert not safe(str(root / "escape.mp4"), str(root))
        (root / "linked-dir").symlink_to(inside.parent, target_is_directory=True)
        assert not safe(str(root / "linked-dir" / "clip.mp4"), str(root))
    except (OSError, NotImplementedError):
        pass


def test_safe_move_collision_never_overwrites_and_repeated_names_are_unique(tmp_path):
    handler = FileHandler()
    destination = tmp_path / "Uploaded" / "clip.mp4"
    first = tmp_path / "one" / "clip.mp4"
    second = tmp_path / "two" / "clip.mp4"
    third = tmp_path / "three" / "clip.mp4"
    write_binary_file(first, b"first")
    write_binary_file(second, b"second")
    write_binary_file(third, b"third")

    assert handler.safe_move(str(first), str(destination))[0]
    assert handler.safe_move(str(second), str(destination))[0]
    assert handler.safe_move(str(third), str(destination))[0]
    archived = sorted(path for path in destination.parent.iterdir() if path.is_file())
    assert len(archived) == 3
    assert {path.read_bytes() for path in archived} == {b"first", b"second", b"third"}


@pytest.mark.skipif(os.name == "nt", reason="POSIX hard-link publication path")
def test_safe_move_retries_if_destination_appears_during_publication(tmp_path, monkeypatch):
    handler = FileHandler()
    source = tmp_path / "source.mp4"
    destination = tmp_path / "Uploaded" / "source.mp4"
    write_binary_file(source, b"source")
    original_publish = handler._publish_without_overwrite
    raced = False

    def publish(staged, target):
        nonlocal raced
        if not raced:
            raced = True
            Path(target).write_bytes(b"racer")
            return False
        return original_publish(staged, target)

    monkeypatch.setattr(handler, "_publish_without_overwrite", publish)
    success, _ = handler.safe_move(str(source), str(destination))
    assert success
    assert destination.read_bytes() == b"racer"
    assert not source.exists()
    assert any(path.read_bytes() == b"source" for path in destination.parent.iterdir() if path.is_file())


def test_safe_move_cleans_incomplete_cross_volume_staging_and_keeps_original(tmp_path, monkeypatch):
    handler = FileHandler()
    source = tmp_path / "source" / "video.mp4"
    destination = tmp_path / "Uploaded" / "video.mp4"
    write_binary_file(source, b"original")
    destination.parent.mkdir()
    monkeypatch.setattr(handler, "_are_on_same_drive", lambda *_: False)

    def incomplete_copy(src, dest, cached_source_hash=None):
        Path(dest).write_bytes(b"partial")
        return False

    monkeypatch.setattr(handler, "safe_copy_and_verify", incomplete_copy)
    success, _ = handler.safe_move(str(source), str(destination))

    assert not success
    assert source.read_bytes() == b"original"
    assert not destination.exists()
    assert list(destination.parent.iterdir()) == []


def test_scanner_prunes_junction_like_directories(tmp_path, monkeypatch):
    root = tmp_path / "watch"
    write_binary_file(root / "keep.mp4", b"keep")
    junction = root / "junction"
    write_binary_file(junction / "skip.mp4", b"skip")
    original_guard = FileHandler._is_link_or_junction
    monkeypatch.setattr(FileHandler, "_is_link_or_junction", staticmethod(
        lambda path: Path(path) == junction or original_guard(path)))

    assert FileHandler().get_video_files(str(root), recursive=True) == ["keep.mp4"]


def test_windows_no_clobber_rename_does_not_delete_source_twice(tmp_path, monkeypatch):
    import file_handler as file_handler_module
    from types import SimpleNamespace

    source = tmp_path / "source.mp4"
    destination = tmp_path / "Uploaded" / "source.mp4"
    write_binary_file(source, b"source")
    platform_os = SimpleNamespace(**vars(os))
    platform_os.name = "nt"

    def windows_rename(src, dest):
        os.link(src, dest)  # Model Windows rename refusing an existing destination.
        os.unlink(src)

    platform_os.rename = windows_rename
    monkeypatch.setattr(file_handler_module, "os", platform_os)
    handler = FileHandler()
    monkeypatch.setattr(handler, "_are_on_same_drive", lambda *_: True)

    success, _ = handler.safe_move(str(source), str(destination))

    assert success
    assert not source.exists()
    assert destination.read_bytes() == b"source"


def test_cross_volume_verified_copy_publishes_then_removes_original(tmp_path, monkeypatch):
    import config

    handler = FileHandler()
    source = tmp_path / "source.mp4"
    destination = tmp_path / "Uploaded" / "source.mp4"
    write_binary_file(source, b"complete video")
    monkeypatch.setattr(handler, "_are_on_same_drive", lambda *_: False)
    monkeypatch.setattr(config, "INITIAL_FILE_OPERATION_DELAY", 0)

    success, _ = handler.safe_move(str(source), str(destination))

    assert success
    assert not source.exists()
    assert destination.read_bytes() == b"complete video"
    assert list(destination.parent.iterdir()) == [destination]


def test_failed_source_removal_preserves_original_and_rolls_back_duplicate(tmp_path, monkeypatch):
    import config

    handler = FileHandler()
    source = tmp_path / "source.mp4"
    destination = tmp_path / "Uploaded" / "source.mp4"
    write_binary_file(source, b"original")
    monkeypatch.setattr(config, "INITIAL_FILE_OPERATION_DELAY", 0)
    monkeypatch.setattr(config, "MAX_FILE_OPERATION_RETRIES", 1)
    # Force the cross-volume copy path, which reaches source removal on Windows
    # as well as POSIX. Same-volume Windows rename consumes the source atomically.
    monkeypatch.setattr(handler, "_are_on_same_drive", lambda *_: False)
    real_remove = os.remove

    def locked_remove(path):
        if os.fspath(path) == str(source):
            raise PermissionError("source locked")
        real_remove(path)

    monkeypatch.setattr(os, "remove", locked_remove)

    success, _ = handler.safe_move(str(source), str(destination))

    assert not success
    assert source.read_bytes() == b"original"
    assert not destination.exists()
