"""SVG-opschoning met een allowlist.

Een blocklist ("geen <script>") mist altijd iets: onload-attributen, foreignObject met
HTML, externe referenties, DTD-entiteiten (XXE). Daarom parsen we met defusedxml (geen
DTD's of entiteiten), houden we alleen bekende SVG-elementen en -attributen over en
schrijven we het resultaat opnieuw uit. Wat niet op de lijst staat, verdwijnt.
"""

import re
import xml.etree.ElementTree as ET

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import fromstring

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
MAX_SVG_BYTES = 2 * 1024 * 1024

ALLOWED_ELEMENTS = {
    "svg", "g", "defs", "symbol", "use", "title", "desc",
    "path", "rect", "circle", "ellipse", "line", "polyline", "polygon",
    "text", "tspan", "textPath",
    "linearGradient", "radialGradient", "stop", "pattern",
    "clipPath", "mask", "filter", "image",
    "feGaussianBlur", "feOffset", "feBlend", "feColorMatrix", "feComposite", "feFlood",
    "feMerge", "feMergeNode", "feDropShadow",
}  # fmt: skip

ALLOWED_ATTRIBUTES = {
    "id", "class", "viewBox", "width", "height", "x", "y", "x1", "y1", "x2", "y2",
    "cx", "cy", "r", "rx", "ry", "d", "points", "transform", "fill", "fill-opacity",
    "fill-rule", "clip-rule", "stroke", "stroke-width", "stroke-opacity", "stroke-linecap",
    "stroke-linejoin", "stroke-dasharray", "stroke-dashoffset", "stroke-miterlimit",
    "opacity", "color", "display", "visibility", "clip-path", "mask", "filter",
    "font-family", "font-size", "font-weight", "font-style", "text-anchor",
    "dominant-baseline", "letter-spacing", "dx", "dy", "rotate", "textLength",
    "offset", "stop-color", "stop-opacity", "gradientUnits", "gradientTransform",
    "spreadMethod", "fx", "fy", "patternUnits", "patternContentUnits", "patternTransform",
    "clipPathUnits", "maskUnits", "maskContentUnits", "preserveAspectRatio",
    "stdDeviation", "in", "in2", "result", "mode", "values", "type", "operator",
    "flood-color", "flood-opacity", "k1", "k2", "k3", "k4", "href", "style", "version",
}  # fmt: skip

# Alleen interne verwijzingen of ingebedde rasterbeelden; nooit externe URL's.
_SAFE_HREF = re.compile(r"^(#[\w.-]+|data:image/(png|jpeg|gif|webp);base64,[A-Za-z0-9+/=\s]+)$")
_UNSAFE_STYLE = re.compile(r"url\s*\(\s*['\"]?(?!#)|expression\s*\(|@import|javascript:", re.I)


class SvgRejected(ValueError):
    pass


# Actieve inhoud: wordt geweigerd in plaats van stil verwijderd, zodat de ontwerper weet
# dat het bestand niet deugt. Overige onbekende elementen (editor-metadata) gaan stil weg.
_ACTIVE_ELEMENTS = {"script", "foreignObject", "iframe", "object", "embed", "a", "animate", "set"}


def _local(tag: str) -> tuple[str | None, str]:
    if tag.startswith("{"):
        ns, _, name = tag[1:].partition("}")
        return ns, name
    return None, tag


def sanitize_svg(data: bytes, *, reject_active: bool = False) -> tuple[bytes, int]:
    """Geeft de opgeschoonde SVG terug plus het aantal verwijderde elementen/attributen.

    Met reject_active=True wordt een SVG met actieve inhoud (scripts, event-attributen,
    foreignObject, javascript:- of externe URL's) geweigerd in plaats van opgeschoond."""
    if len(data) > MAX_SVG_BYTES:
        raise SvgRejected("SVG is groter dan 2 MB.")
    try:
        root = fromstring(data, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except (DefusedXmlException, ET.ParseError) as error:
        raise SvgRejected(
            f"Dit SVG-bestand is niet veilig te lezen ({type(error).__name__})."
        ) from error
    ns, name = _local(root.tag)
    if name != "svg" or ns not in (SVG_NS, None):
        raise SvgRejected("Dit bestand is geen SVG.")
    if reject_active:
        reason = _active_content(root)
        if reason:
            raise SvgRejected(f"SVG met actieve inhoud is niet toegestaan ({reason}).")
    removed = _clean(root)
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)
    cleaned = ET.tostring(root, encoding="utf-8", xml_declaration=False)
    if not cleaned.strip():
        raise SvgRejected("Na opschonen bleef er niets over.")
    return cleaned, removed


def _active_content(root: ET.Element) -> str | None:
    for element in root.iter():
        _, name = _local(element.tag)
        if name in _ACTIVE_ELEMENTS:
            return f"<{name}>"
        for attr, value in element.attrib.items():
            _, attr_name = _local(attr)
            if attr_name.lower().startswith("on"):
                return f"{attr_name}-attribuut"
            if attr_name == "href" and not _SAFE_HREF.match(value.strip()):
                return "externe of javascript-verwijzing"
            if attr_name == "style" and _UNSAFE_STYLE.search(value):
                return "externe verwijzing in style"
    return None


def _clean(element: ET.Element) -> int:
    removed = 0
    for child in list(element):
        ns, name = _local(child.tag)
        if ns not in (SVG_NS, None) or name not in ALLOWED_ELEMENTS:
            element.remove(child)
            removed += 1
            continue
        removed += _clean(child)
    for attr in list(element.attrib):
        ns, name = _local(attr)
        value = element.attrib[attr]
        keep = name in ALLOWED_ATTRIBUTES and ns in (None, XLINK_NS)
        if keep and name == "href":
            keep = bool(_SAFE_HREF.match(value.strip()))
        if keep and name == "style":
            keep = not _UNSAFE_STYLE.search(value)
        if keep and value.strip().lower().startswith("javascript:"):
            keep = False
        if not keep:
            del element.attrib[attr]
            removed += 1
    return removed
