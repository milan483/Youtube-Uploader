import os
from pathlib import Path

import pytest

from file_handler import FileHandler
from services.uploaded_clips_manager import UploadedClipsManager


def make_clip(watch_root, name, payload=b"video"):
    path = watch_root / "Uploaded" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def test_lists_recursive_archives_and_totals_without_hidden_staging(tmp_path):
    root = tmp_path / "watch"
    root.mkdir()
    make_clip(root, "Game A/clip.mp4", b"aa")
    make_clip(root, "Game B/clip.mp4", b"bbbb")
    make_clip(root, "clip.mov", b"xxx")
    make_clip(root, ".upload-staging-123.part", b"partial")
    make_clip(root, "notes.txt", b"not a clip")
    manager = UploadedClipsManager(FileHandler(), trash_func=lambda p: None)

    clips = manager.list_clips(str(root))

    assert {c.relative_path for c in clips} == {
        os.path.join("Game A", "clip.mp4"),
        os.path.join("Game B", "clip.mp4"),
        "clip.mov",
    }
    assert sum(c.size_bytes for c in clips) == 9


def test_empty_archive_and_missing_archive_directory_are_safe(tmp_path):
    root = tmp_path / "watch"
    root.mkdir()
    manager = UploadedClipsManager(FileHandler(), trash_func=lambda p: None)
    assert manager.list_clips(str(root)) == []
    assert not (root / "Uploaded").exists()


def test_recycles_only_selected_archived_clips(tmp_path):
    root = tmp_path / "watch"
    root.mkdir()
    a = make_clip(root, "Game A/clip.mp4", b"a")
    b = make_clip(root, "Game B/clip.mp4", b"b")
    calls = []

    def trash(path):
        calls.append(path)
        Path(path).unlink()

    manager = UploadedClipsManager(FileHandler(), trash_func=trash)
    result = manager.delete_clips(str(root), [os.path.join("Game A", "clip.mp4")])

    assert result.deleted == (os.path.join("Game A", "clip.mp4"),)
    assert not result.failed
    assert calls == [str(a)]
    assert not a.exists() and b.exists()


def test_partial_trash_failure_does_not_delete_other_clips(tmp_path):
    root = tmp_path / "watch"
    root.mkdir()
    a = make_clip(root, "a.mp4")
    b = make_clip(root, "b.mp4")
    def trash(path):
        if path == str(a):
            raise PermissionError("locked file")
        Path(path).unlink()

    manager = UploadedClipsManager(FileHandler(), trash_func=trash)
    result = manager.delete_clips(str(root), ["a.mp4", "b.mp4"])

    assert result.deleted == ("b.mp4",)
    assert "locked file" in result.failed["a.mp4"]
    assert a.exists() and not b.exists()


@pytest.mark.parametrize("invalid", [
    "../outside.mp4", "../../outside.mp4", "/etc/passwd",
    "C:\\other.mp4", "..\\outside.mp4", ".upload-staging-abc.part",
    "notes.txt",
])
def test_rejects_traversal_external_and_nonvideo_targets(tmp_path, invalid):
    root = tmp_path / "watch"
    root.mkdir()
    make_clip(root, "safe.mp4")
    external = tmp_path / "outside.mp4"
    external.write_bytes(b"external")
    calls = []
    manager = UploadedClipsManager(FileHandler(), trash_func=calls.append)

    result = manager.delete_clips(str(root), [invalid])

    assert not result.deleted
    assert invalid in result.failed
    assert calls == []
    assert external.read_bytes() == b"external"


def test_does_not_follow_symlinks_for_listing_or_deletion(tmp_path):
    root = tmp_path / "watch"
    root.mkdir()
    real = make_clip(root, "normal.mp4")
    other = tmp_path / "other.mp4"
    other.write_bytes(b"other")
    link = root / "Uploaded" / "linked.mp4"
    try:
        link.symlink_to(other)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks unavailable on this platform")

    calls = []
    manager = UploadedClipsManager(FileHandler(), trash_func=calls.append)
    assert [c.relative_path for c in manager.list_clips(str(root))] == ["normal.mp4"]
    result = manager.delete_clips(str(root), ["linked.mp4"])

    assert not result.deleted
    assert "linked.mp4" in result.failed
    assert calls == []
    assert other.read_bytes() == b"other"
    assert real.exists()


def test_stale_selection_revalidated_before_trash(tmp_path):
    root = tmp_path / "watch"
    root.mkdir()
    file = make_clip(root, "clip.mp4")
    calls = []
    manager = UploadedClipsManager(FileHandler(), trash_func=calls.append)
    selection = manager.list_clips(str(root))
    file.unlink()

    result = manager.delete_clips(str(root), [selection[0].relative_path])

    assert not result.deleted and "clip.mp4" in result.failed
    assert calls == []


def test_changing_main_ui_folder_cannot_retarget_snapshot(tmp_path):
    a = tmp_path / "A"
    b = tmp_path / "B"
    a.mkdir()
    b.mkdir()
    source_a = make_clip(a, "clip.mp4", b"a")
    source_b = make_clip(b, "clip.mp4", b"b")
    manager = UploadedClipsManager(FileHandler(), trash_func=lambda p: Path(p).unlink())
    snapshot = str(a)

    result = manager.delete_clips(snapshot, ["clip.mp4"])

    assert result.deleted == ("clip.mp4",)
    assert not source_a.exists() and source_b.exists()
