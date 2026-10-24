"""Inname van beeldbestanden: type bepalen, afmetingen lezen en naar sRGB omzetten.

Chromium rendert in sRGB zonder profiel te lezen op een consistente manier; foto's in
Display P3, Adobe RGB of CMYK zouden anders verschoven kleuren geven. Het origineel blijft
bewaard, de werkkopie is altijd sRGB.
"""

import io
from dataclasses import dataclass

from PIL import Image, ImageCms, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()

SVG_MIME = "image/svg+xml"
FONT_TYPES = {".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf", ".otf": "font/otf"}
MAX_PIXELS = 80_000_000


class UnsupportedFile(ValueError):
    pass


@dataclass
class IngestedImage:
    data: bytes
    mime: str
    extension: str
    width: int | None
    height: int | None
    color_profile: str | None
    converted: bool


def _profile_name(image: Image.Image) -> str | None:
    icc = image.info.get("icc_profile")
    if not icc:
        return None
    try:
        profile = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        return ImageCms.getProfileDescription(profile).strip() or "onbekend profiel"
    except (OSError, ImageCms.PyCMSError):
        return "onleesbaar profiel"


def _to_srgb(image: Image.Image) -> tuple[Image.Image, bool]:
    icc = image.info.get("icc_profile")
    has_alpha = image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)
    target_mode = "RGBA" if has_alpha else "RGB"
    srgb = ImageCms.createProfile("sRGB")

    if icc:
        source = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        base = image.convert("RGBA" if has_alpha else image.mode if image.mode == "CMYK" else "RGB")
        converted = ImageCms.profileToProfile(base, source, srgb, outputMode=target_mode)
        return converted, True

    if image.mode == "CMYK":
        # CMYK zonder profiel: naieve omzetting, kleuren kunnen afwijken.
        return image.convert("RGB"), True
    return image.convert(target_mode), image.mode not in ("RGB", "RGBA")


def ingest_image(data: bytes, filename: str) -> IngestedImage:
    lower = filename.lower()
    if lower.endswith(".svg"):
        if b"<svg" not in data[:2048].lower():
            raise UnsupportedFile("Dit SVG-bestand lijkt geen geldige SVG.")
        if b"<script" in data.lower():
            raise UnsupportedFile("SVG met scripts is niet toegestaan.")
        return IngestedImage(data, SVG_MIME, ".svg", None, None, None, False)

    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (OSError, Image.DecompressionBombError) as error:
        raise UnsupportedFile(f"Bestand is geen leesbaar beeld: {error}") from error

    image = ImageOps.exif_transpose(image)
    profile = _profile_name(image)
    converted_image, converted = _to_srgb(image)

    output = io.BytesIO()
    if converted_image.mode == "RGBA":
        converted_image.save(
            output,
            "PNG",
            icc_profile=ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes(),
        )
        mime, extension = "image/png", ".png"
    else:
        converted_image.save(
            output,
            "JPEG",
            quality=95,
            subsampling=0,
            icc_profile=ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes(),
        )
        mime, extension = "image/jpeg", ".jpg"

    return IngestedImage(
        data=output.getvalue(),
        mime=mime,
        extension=extension,
        width=converted_image.width,
        height=converted_image.height,
        color_profile=profile,
        converted=converted or bool(profile and "srgb" not in profile.lower()),
    )


def font_mime(filename: str) -> str:
    for extension, mime in FONT_TYPES.items():
        if filename.lower().endswith(extension):
            return mime
    raise UnsupportedFile("Alleen .woff2, .woff, .ttf of .otf zijn toegestaan als font.")
