from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 15 * 1024 * 1024
MAX_PIXELS = 25_000_000


class InvalidImage(ValueError):
    pass


def read_image(source: bytes | Path, *, query: bool = True) -> Image.Image:
    if isinstance(source, Path):
        if query and source.stat().st_size > MAX_BYTES:
            raise InvalidImage("Image exceeds 15 MB")
        source = source.read_bytes()
    if query and len(source) > MAX_BYTES:
        raise InvalidImage("Image exceeds 15 MB")
    try:
        with Image.open(BytesIO(source)) as image:
            if query and image.format not in {"JPEG", "PNG", "WEBP"}:
                raise InvalidImage("Only JPEG, PNG and WebP queries are supported")
            if image.width * image.height > MAX_PIXELS:
                raise InvalidImage("Image exceeds 25 million pixels")
            image.load()
            return ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise InvalidImage("Corrupt or unsupported image") from exc
