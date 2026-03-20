import hashlib
from pathlib import Path

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
