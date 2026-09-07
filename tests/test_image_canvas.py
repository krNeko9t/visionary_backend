from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from visionary_tasks.domain.jobs import JobSpec
from visionary_tasks.jobs.image_canvas import unify_image_canvases
from visionary_tasks.jobs.image_names import ascii_image_filenames
from visionary_tasks.jobs.paths import JobPaths
from visionary_tasks.services.ingest import ingest_job_files


def _png_bytes(width: int, height: int, color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (width, height), color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_unify_image_canvases_pads_to_max_size_without_stretching():
    red = _png_bytes(4, 2, (255, 0, 0))
    blue = _png_bytes(2, 4, (0, 0, 255))

    unified = unify_image_canvases([("a.png", red), ("b.png", blue)])
    sizes = []
    for filename, content in unified:
        image = Image.open(BytesIO(content))
        sizes.append((filename, image.size))
        assert image.mode == "RGB"
        if filename == "a.png":
            assert image.getpixel((0, 1)) == (255, 0, 0)
            assert image.getpixel((0, 0)) == (0, 0, 0)
        else:
            assert image.getpixel((1, 0)) == (0, 0, 255)
            assert image.getpixel((0, 0)) == (0, 0, 0)

    assert sizes == [("a.png", (4, 4)), ("b.png", (4, 4))]


def test_unify_image_canvases_keeps_identical_rgb_bytes():
    payload = _png_bytes(3, 3, (10, 20, 30))
    unified = unify_image_canvases([("keep.png", payload), ("same.png", payload)])
    assert unified[0][1] == payload
    assert unified[1][1] == payload


def test_unify_image_canvases_rejects_invalid_image():
    with pytest.raises(ValueError, match="无法解码图像"):
        unify_image_canvases([("bad.png", b"not-an-image")])


def test_ingest_images_writes_unified_canvas(tmp_path: Path):
    paths = JobPaths(job_id="job1", root=tmp_path / "job1")
    paths.ensure_layout()
    spec = JobSpec(outputs=["point_cloud"])
    ingest_job_files(
        spec,
        [("wide.png", _png_bytes(6, 2, (255, 0, 0))), ("tall.png", _png_bytes(2, 4, (0, 255, 0)))],
        paths,
        "output",
    )
    sizes = {path.name: Image.open(path).size for path in paths.input_dir.glob("*.png")}
    assert sizes == {"wide.png": (6, 4), "tall.png": (6, 4)}


def test_ascii_image_filenames_renames_non_ascii_and_keeps_safe_names():
    payload = _png_bytes(2, 2, (1, 2, 3))
    renamed = ascii_image_filenames(
        [("摆件1.png", payload), ("photo.jpg", payload), ("摆件2.png", payload)]
    )
    assert [name for name, _ in renamed] == ["img_0001.png", "photo.jpg", "img_0003.png"]


def test_ascii_image_filenames_avoids_collision_with_kept_name():
    payload = _png_bytes(2, 2, (1, 2, 3))
    renamed = ascii_image_filenames(
        [("img_0001.png", payload), ("场景.png", payload)]
    )
    assert [name for name, _ in renamed] == ["img_0001.png", "img_0002.png"]


def test_ingest_images_renames_non_ascii_filenames(tmp_path: Path):
    paths = JobPaths(job_id="job1", root=tmp_path / "job1")
    paths.ensure_layout()
    spec = JobSpec(outputs=["point_cloud"])
    ingest_job_files(
        spec,
        [("摆件1.png", _png_bytes(4, 2, (255, 0, 0))), ("摆件2.png", _png_bytes(2, 4, (0, 255, 0)))],
        paths,
        "output",
    )
    names = sorted(path.name for path in paths.input_dir.glob("*.png"))
    assert names == ["img_0001.png", "img_0002.png"]
    sizes = {path.name: Image.open(path).size for path in paths.input_dir.glob("*.png")}
    assert sizes == {"img_0001.png": (4, 4), "img_0002.png": (4, 4)}
