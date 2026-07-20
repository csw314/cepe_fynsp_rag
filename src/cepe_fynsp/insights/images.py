"""Secure decoding, validation, metadata stripping, and re-encoding of chart captures."""

from __future__ import annotations

import base64
import binascii
import hashlib
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, UnidentifiedImageError

from cepe_fynsp.insights.schemas import ChartImageInput

MAX_DECODED_IMAGE_BYTES = 4_000_000
MAX_IMAGE_PIXELS = 4_000_000
MAX_IMAGE_DIMENSION = 2400


class InvalidChartImageError(ValueError):
    """Raised when an untrusted browser capture violates image limits."""


@dataclass(frozen=True)
class ValidatedChartImage:
    """Sanitized PNG bytes and authoritative metadata safe for AskSage upload."""

    content: bytes
    width: int
    height: int
    sha256: str
    mime_type: str = "image/png"


def validate_chart_image(image_input: ChartImageInput) -> ValidatedChartImage:
    """Decode an untrusted base64 PNG, enforce bounds, strip metadata, and re-encode it."""
    try:
        decoded = base64.b64decode(image_input.data_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise InvalidChartImageError("The visualization image is not valid base64.") from exc
    if not decoded or len(decoded) > MAX_DECODED_IMAGE_BYTES:
        raise InvalidChartImageError("The visualization image exceeds the allowed size.")
    if hashlib.sha256(decoded).hexdigest() != image_input.sha256:
        raise InvalidChartImageError("The visualization image hash does not match its content.")
    try:
        with Image.open(BytesIO(decoded)) as source:
            source.load()
            if source.format != "PNG":
                raise InvalidChartImageError("Only PNG visualization images are accepted.")
            width, height = source.size
            if (width, height) != (image_input.width, image_input.height):
                raise InvalidChartImageError(
                    "The visualization image dimensions do not match its metadata."
                )
            if (
                width > MAX_IMAGE_DIMENSION
                or height > MAX_IMAGE_DIMENSION
                or width * height > MAX_IMAGE_PIXELS
            ):
                raise InvalidChartImageError("The visualization image dimensions are too large.")
            cleaned = source.convert("RGBA" if "A" in source.getbands() else "RGB")
            output = BytesIO()
            cleaned.save(output, format="PNG", optimize=True)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise InvalidChartImageError("The visualization image is malformed.") from exc
    sanitized = output.getvalue()
    if len(sanitized) > MAX_DECODED_IMAGE_BYTES:
        raise InvalidChartImageError("The sanitized visualization image exceeds the size limit.")
    return ValidatedChartImage(
        content=sanitized,
        width=width,
        height=height,
        sha256=hashlib.sha256(sanitized).hexdigest(),
    )
