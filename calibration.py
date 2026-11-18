# Copyright (C) 2026 David
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
"""
Read the pixel size of a microscope image from its file, with Pillow
only (no tifffile), so it works inside the Inkscape Flatpak.

Supported, in the order they are tried:

- OME-TIFF: OME-XML Pixels PhysicalSizeX/Y and their units (default µm).
- ImageJ/Fiji TIFF: "unit=" in the ImageJ description and the X/Y
  resolution tags, which hold pixels per unit.
- Thermo Fisher/FEI SEM and FIB (tags 34680 and 34682, INI text):
  [Scan] PixelWidth/PixelHeight in metres, else [IRBeam] HFW/VFW divided
  by [Image] ResolutionX/Y.
- Zeiss SEM (tag 34118): the fourth unnamed value, the pixel size in
  metres at 1024 pixels wide, times 1024 / image width.
- Gatan DigitalMicrograph TIFF: tags 65009/65010 (scale), 65003 (unit).
- JEOL SightX TEM in MAG mode: resolution tags at the camera divided by
  the magnification from its TemReporter XML.

The vendor rules follow RosettaSciIO's TIFF reader (rsciio/tiff/_api.py,
GPL-3.0), and are checked against its test files with the values its
tests expect. The plain TIFF resolution tags are not used: exported
images usually carry a print resolution there (72 or 300 dpi), not a
calibration.
"""

import io
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from PIL import Image

# metres per unit
UNITS = {
    "km": 1e3,
    "m": 1.0,
    "cm": 1e-2,
    "mm": 1e-3,
    "µm": 1e-6,
    "μm": 1e-6,  # Greek mu
    "um": 1e-6,
    "micron": 1e-6,
    "microns": 1e-6,
    "\\u00b5m": 1e-6,  # as ImageJ writes µm in its description
    "nm": 1e-9,
    "pm": 1e-12,
    "å": 1e-10,
    "Å": 1e-10,
    "angstrom": 1e-10,
    "in": 0.0254,
    "inch": 0.0254,
}

TAG_DESCRIPTION = 270
TAG_MAKE = 271
TAG_XRES = 282
TAG_YRES = 283
TAG_RESUNIT = 296
TAG_CZ_SEM = 34118
TAG_FEI = (34682, 34680)  # FEI_HELIOS, FEI_SFEG
TAG_DM_UNIT = 65003
TAG_DM_SCALE_X = 65009
TAG_DM_SCALE_Y = 65010


@dataclass
class Calibration:
    """Pixel size in metres, and where it came from."""

    x: float
    y: float
    source: str

    def __post_init__(self):
        if not (self.x > 0 and self.y > 0):
            raise ValueError("pixel size must be positive")


def metres_per_unit(unit):
    """Metres in one `unit`, or None if it is not a length."""
    if unit is None:
        return None
    unit = str(unit).strip()
    try:  # Pillow reads TIFF text as Latin-1: undo a UTF-8 "µ" read that way
        unit = unit.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return UNITS.get(unit, UNITS.get(unit.lower()))


def read(source):
    """Calibration of an image file (a path, bytes or a file object), or
    None when the file has none that we can read."""
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    try:
        image = Image.open(source)
    except (OSError, ValueError):
        return None
    with image:
        tags = getattr(image, "tag_v2", None)
        if tags is None:
            return None  # not a TIFF
        width = image.size[0]
        for reader in (_ome, _imagej, _fei, _zeiss_sem, _digital_micrograph, _jeol):
            try:
                found = reader(tags, width)
            except (ValueError, KeyError, IndexError, TypeError, ET.ParseError):
                found = None
            if found is not None:
                return found
    return None


def _text(tags, tag):
    value = tags.get(tag)
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    return str(value)


def _ome(tags, width):
    text = _text(tags, TAG_DESCRIPTION)
    if not text or "<OME" not in text:
        return None
    root = ET.fromstring(text.strip())
    pixels = next(
        (e for e in root.iter() if e.tag.rsplit("}", 1)[-1] == "Pixels"), None
    )
    if pixels is None or pixels.get("PhysicalSizeX") is None:
        return None
    size_x = float(pixels.get("PhysicalSizeX"))
    size_y = float(pixels.get("PhysicalSizeY", size_x))
    unit_x = metres_per_unit(pixels.get("PhysicalSizeXUnit", "µm"))
    unit_y = metres_per_unit(
        pixels.get("PhysicalSizeYUnit", pixels.get("PhysicalSizeXUnit", "µm"))
    )
    if unit_x is None or unit_y is None:
        return None
    return Calibration(size_x * unit_x, size_y * unit_y, "OME-TIFF")


def _imagej(tags, width):
    text = _text(tags, TAG_DESCRIPTION)
    if not text or not text.startswith("ImageJ="):
        return None
    fields = dict(line.split("=", 1) for line in text.splitlines() if "=" in line)
    unit = metres_per_unit(fields.get("unit"))
    if unit is None or TAG_XRES not in tags:
        return None  # no unit, or "pixel": not calibrated
    x_res = float(tags[TAG_XRES])  # pixels per unit
    y_res = float(tags.get(TAG_YRES, x_res))
    return Calibration(unit / x_res, unit / y_res, "ImageJ")


def _ini(text):
    sections, section = {}, None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            section = sections.setdefault(line[1:-1], {})
        elif "=" in line and section is not None:
            key, value = line.split("=", 1)
            section[key.strip()] = value.strip()
    return sections


def _fei(tags, width):
    text = next((_text(tags, t) for t in TAG_FEI if t in tags), None)
    if not text:
        return None
    ini = _ini(text)
    scan = ini.get("Scan", {})
    if "PixelWidth" in scan:
        size_x = float(scan["PixelWidth"])
        size_y = float(scan.get("PixelHeight", size_x))
        return Calibration(size_x, size_y, "Thermo Fisher/FEI")
    beam, image = ini.get("IRBeam", {}), ini.get("Image", {})
    if "HFW" in beam and "ResolutionX" in image:
        size_x = float(beam["HFW"]) / float(image["ResolutionX"])
        size_y = float(beam.get("VFW", 0) or 0) / float(
            image.get("ResolutionY", 1) or 1
        )
        return Calibration(size_x, size_y or size_x, "Thermo Fisher/FEI (IRBeam)")
    return None


def _zeiss_sem(tags, width):
    text = _text(tags, TAG_CZ_SEM)
    if not text:
        return None
    # The tag starts with unnamed numbers (tifffile's read_cz_sem collects
    # every line that is neither a section name in capitals nor the line
    # after one); the fourth is the pixel size in metres at 1024 wide.
    unnamed, after_key = [], False
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.isupper():
            after_key = True
        elif after_key:
            after_key = False
        else:
            unnamed.append(line)
    size = float(unnamed[3]) * 1024 / width
    return Calibration(size, size, "Zeiss SEM")


def _digital_micrograph(tags, width):
    if TAG_DM_SCALE_X not in tags:
        return None
    unit = metres_per_unit(_text(tags, TAG_DM_UNIT))
    if unit is None:
        return None
    size_x = float(tags[TAG_DM_SCALE_X])
    size_y = float(tags.get(TAG_DM_SCALE_Y, size_x))
    return Calibration(size_x * unit, size_y * unit, "Gatan DigitalMicrograph")


def _jeol(tags, width):
    if _text(tags, TAG_MAKE) != "JEOL Ltd.":
        return None
    text = _text(tags, TAG_DESCRIPTION)
    xml = "".join(line.strip(" \r\n\t\x01\x00") for line in text.split("\n"))
    root = ET.fromstring(xml)
    if root.findtext("Eos/EosMode") != "eosTEM":
        return None  # STEM: not handled
    if root.findtext("ImageFormingSystem/ModeString") != "MAG":
        return None  # diffraction: reciprocal units, no scale bar
    magnification = float(root.findtext("ImageFormingSystem/SelectorValue"))
    per_unit = 0.0254 if int(tags.get(TAG_RESUNIT, 2)) == 2 else 0.01  # inch or cm
    size_x = per_unit / float(tags[TAG_XRES]) / magnification
    size_y = per_unit / float(tags.get(TAG_YRES, tags[TAG_XRES])) / magnification
    return Calibration(size_x, size_y, "JEOL SightX")


def format_length(metres, digits=4):
    """'2.615 µm' style text for a length in metres."""
    for unit, size in (
        ("m", 1),
        ("mm", 1e-3),
        ("µm", 1e-6),
        ("nm", 1e-9),
        ("pm", 1e-12),
    ):
        if metres >= size:
            return f"{metres / size:.{digits}g} {unit}"
    return f"{metres:.{digits}g} m"


def parse_length(text):
    """Metres in a length such as '0.5 µm' or '200nm'."""
    match = re.fullmatch(r"\s*([0-9.eE+-]+)\s*([^\s0-9]+)\s*", text or "")
    if not match:
        raise ValueError(f"not a length: {text!r}")
    unit = metres_per_unit(match.group(2))
    if unit is None:
        raise ValueError(f"unknown unit in {text!r}")
    return float(match.group(1)) * unit
