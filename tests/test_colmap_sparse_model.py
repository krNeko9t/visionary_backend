import struct
from pathlib import Path

from convert import promote_largest_sparse_model, registered_image_count


def _write_images_bin(path: Path, count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(struct.pack("<Q", count))


def test_promote_largest_sparse_model_swaps_best_into_zero(tmp_path: Path):
    sparse = tmp_path / "sparse"
    _write_images_bin(sparse / "0" / "images.bin", 2)
    _write_images_bin(sparse / "1" / "images.bin", 32)
    _write_images_bin(sparse / "2" / "images.bin", 8)

    selected = promote_largest_sparse_model(str(sparse))

    assert selected == str(sparse / "0")
    assert registered_image_count(str(sparse / "0")) == 32
    assert registered_image_count(str(sparse / "1")) == 2
    assert registered_image_count(str(sparse / "2")) == 8


def test_promote_largest_sparse_model_keeps_zero_when_largest(tmp_path: Path):
    sparse = tmp_path / "sparse"
    _write_images_bin(sparse / "0" / "images.bin", 40)
    _write_images_bin(sparse / "1" / "images.bin", 3)

    promote_largest_sparse_model(str(sparse))

    assert registered_image_count(str(sparse / "0")) == 40
    assert registered_image_count(str(sparse / "1")) == 3
