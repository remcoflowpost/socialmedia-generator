import io

import pytest
from PIL import Image, ImageCms

from app.domain.images import UnsupportedFile, ingest_image


def encode(image: Image.Image, fmt: str, **kwargs) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, fmt, **kwargs)
    return buffer.getvalue()


def test_jpeg_gets_dimensions_and_srgb_profile() -> None:
    result = ingest_image(encode(Image.new("RGB", (1200, 800), "#336699"), "JPEG"), "foto.jpg")
    assert (result.width, result.height, result.mime) == (1200, 800, "image/jpeg")
    embedded = Image.open(io.BytesIO(result.data)).info["icc_profile"]
    description = ImageCms.getProfileDescription(ImageCms.ImageCmsProfile(io.BytesIO(embedded)))
    assert "srgb" in description.lower()


def test_cmyk_is_converted_to_rgb() -> None:
    result = ingest_image(
        encode(Image.new("CMYK", (100, 50), (0, 255, 255, 0)), "JPEG"), "drukwerk.jpg"
    )
    assert result.converted
    assert Image.open(io.BytesIO(result.data)).mode == "RGB"


def test_alpha_is_kept_as_png() -> None:
    result = ingest_image(
        encode(Image.new("RGBA", (64, 64), (255, 0, 0, 128)), "PNG"), "element.png"
    )
    assert result.mime == "image/png"
    assert Image.open(io.BytesIO(result.data)).mode == "RGBA"


def test_exif_rotation_is_applied() -> None:
    image = Image.new("RGB", (400, 200))
    exif = image.getexif()
    exif[0x0112] = 6  # 90 graden gedraaid
    result = ingest_image(encode(image, "JPEG", exif=exif), "telefoon.jpg")
    assert (result.width, result.height) == (200, 400)


def test_svg_with_script_is_rejected() -> None:
    with pytest.raises(UnsupportedFile):
        ingest_image(
            b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', "logo.svg"
        )


def test_non_image_is_rejected() -> None:
    with pytest.raises(UnsupportedFile):
        ingest_image(b"geen beeld", "notities.jpg")
