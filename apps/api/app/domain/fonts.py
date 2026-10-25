"""Fontcontrole bij upload: is het echt een font, en mag het ingesloten worden?

Merkfonts zijn vaak commercieel gelicentieerd. Het OS/2-veld fsType geeft aan wat de
maker toestaat. "Restricted license embedding" (bit 1) betekent dat het font niet in
documenten of renders ingesloten mag worden; dat weigeren we met uitleg. Dit vervangt geen
licentiecontrole: een font zonder beperking in fsType kan nog steeds een licentie hebben
die gebruik op een server verbiedt.
"""

import io
from dataclasses import dataclass

from fontTools.ttLib import TTFont

FONT_MIME = {"woff2": "font/woff2", "woff": "font/woff", "ttf": "font/ttf", "otf": "font/otf"}
MAX_FONT_BYTES = 15 * 1024 * 1024


class FontRejected(ValueError):
    pass


@dataclass
class FontInfo:
    mime: str
    extension: str
    family: str
    subfamily: str
    embedding: str


def _sniff(data: bytes) -> str | None:
    head = data[:4]
    if head == b"wOF2":
        return "woff2"
    if head == b"wOFF":
        return "woff"
    if head == b"OTTO":
        return "otf"
    if head in (b"\x00\x01\x00\x00", b"true"):
        return "ttf"
    return None


def _embedding(fs_type: int) -> str:
    if fs_type & 0x0002 and not fs_type & 0x000C:
        return "restricted"
    if fs_type & 0x0004:
        return "preview_print"
    if fs_type & 0x0008:
        return "editable"
    return "installable"


def inspect_font(data: bytes) -> FontInfo:
    if len(data) > MAX_FONT_BYTES:
        raise FontRejected("Fontbestand is groter dan 15 MB.")
    kind = _sniff(data)
    if not kind:
        raise FontRejected("Dit is geen fontbestand (verwacht WOFF2, WOFF, TTF of OTF).")
    try:
        font = TTFont(io.BytesIO(data), lazy=True)
        name_table = font["name"]
        family = name_table.getBestFamilyName() or ""
        subfamily = name_table.getBestSubFamilyName() or ""
        fs_type = int(font["OS/2"].fsType) if "OS/2" in font else 0
    except Exception as error:  # noqa: BLE001 - fontTools/brotli werpen allerlei fouten
        # Een kapot bestand van een gebruiker is geen serverfout: altijd een nette 415.
        raise FontRejected("Het fontbestand is beschadigd of onleesbaar.") from error
    embedding = _embedding(fs_type)
    if embedding == "restricted":
        raise FontRejected(
            f"{family or 'Dit font'} staat insluiten niet toe (restricted license embedding). "
            "Vraag bij de klant of foundry een webfont- of serverlicentie op."
        )
    return FontInfo(FONT_MIME[kind], f".{kind}", family[:200], subfamily[:100], embedding)
