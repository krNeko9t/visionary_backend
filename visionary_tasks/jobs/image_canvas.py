from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

_PAD_COLOR = (0, 0, 0)
_JPEG_SUFFIXES = {".jpg", ".jpeg"}
_SAVE_FORMATS = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".bmp": "BMP",
    ".webp": "WEBP",
}


@dataclass(frozen=True)
class _LoadedImage:
    filename: str
    original: bytes
    image: Image.Image
    needs_rewrite: bool


def unify_image_canvases(files: list[tuple[str, bytes]]) -> list[tuple[str, bytes]]:
    loaded = [_load_image(filename, content) for filename, content in files]
    canvas = (
        max(item.image.width for item in loaded),
        max(item.image.height for item in loaded),
    )
    return [_export_image(item, canvas) for item in loaded]


def _load_image(filename: str, content: bytes) -> _LoadedImage:
    try:
        with Image.open(BytesIO(content)) as source:
            oriented = ImageOps.exif_transpose(source)
            working = oriented if oriented is not None else source
            rgb, converted = _as_rgb(working)
            image = rgb.copy()
            needs_rewrite = converted or working is not source
    except UnidentifiedImageError as exc:
        raise ValueError(f"无法解码图像: {filename}") from exc
    except OSError as exc:
        raise ValueError(f"无法解码图像: {filename}") from exc
    return _LoadedImage(
        filename=filename,
        original=content,
        image=image,
        needs_rewrite=needs_rewrite,
    )


def _as_rgb(image: Image.Image) -> tuple[Image.Image, bool]:
    if image.mode == "RGB":
        return image, False
    if image.mode in {"RGBA", "LA"}:
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, _PAD_COLOR)
        background.paste(rgba, mask=rgba.split()[-1])
        return background, True
    return image.convert("RGB"), True


def _export_image(item: _LoadedImage, canvas: tuple[int, int]) -> tuple[str, bytes]:
    if item.image.size == canvas and not item.needs_rewrite:
        return item.filename, item.original
    padded = _pad_to_canvas(item.image, canvas)
    return item.filename, _encode_image(item.filename, padded)


def _pad_to_canvas(image: Image.Image, canvas: tuple[int, int]) -> Image.Image:
    width, height = canvas
    if image.size == canvas:
        return image
    padded = Image.new("RGB", canvas, _PAD_COLOR)
    offset = ((width - image.width) // 2, (height - image.height) // 2)
    padded.paste(image, offset)
    return padded


def _encode_image(filename: str, image: Image.Image) -> bytes:
    suffix = Path(filename).suffix.lower()
    image_format = _SAVE_FORMATS.get(suffix, "PNG")
    buffer = BytesIO()
    save_kwargs: dict[str, object] = {}
    if suffix in _JPEG_SUFFIXES:
        save_kwargs["quality"] = 95
        save_kwargs["subsampling"] = 0
    image.save(buffer, format=image_format, **save_kwargs)
    return buffer.getvalue()
