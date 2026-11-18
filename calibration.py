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
- Nikon NIS-Elements: dCalibration (micrometres) in the CLx Lite metadata
  of tag 65331, if bCalibrated.
- Leica LAS X exports (description <LMSIOManager>): resolution tags in
  centimetres. Old Leica TCS: Voxel-Width/Height in the description.
- Hamamatsu NDPI (Make Hamamatsu, tag 65420): resolution tags in cm.
- FluoView (and Andor iQ, same header): tag 34361, the X and Y
  dimension records.
- Olympus/Evident cellSens, analySIS (tag 33560, the SIS block, on any
  page): x and y calibration times 10 to the power of its exponent.
- Zeiss ZEN, from a sidecar <image>_metadata.xml next to the image:
  Scaling/Items/Distance X and Y, in metres.

The vendor rules follow RosettaSciIO's TIFF reader (rsciio/tiff/_api.py,
GPL-3.0), and are checked against its test files with the values its
tests expect. The plain TIFF resolution tags are not used: exported
images usually carry a print resolution there (72 or 300 dpi), not a
calibration.
"""

import io
import os
import re
import struct
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


def read(source, path=None):
    """Calibration of an image file (a path, bytes or a file object), or
    None when the file has none that we can read. `path` (the image's
    file, when `source` is its bytes) lets a sidecar file next to it be
    read too."""
    if isinstance(source, str):
        path = path or source
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    errors = (
        ValueError,
        KeyError,
        IndexError,
        TypeError,
        ET.ParseError,
        struct.error,
        OSError,
    )
    try:
        image = Image.open(source)
    except (OSError, ValueError):
        return _sidecar(path)
    with image:
        tags = getattr(image, "tag_v2", None)
        if tags is None:
            return _sidecar(path)  # not a TIFF
        width = image.size[0]
        for reader in (
            _ome,
            _imagej,
            _fei,
            _zeiss_sem,
            _digital_micrograph,
            _jeol,
            _nikon,
            _leica_las_x,
            _leica_tcs,
            _hamamatsu_ndpi,
        ):
            try:
                found = reader(tags, width)
            except errors:
                found = None
            if found is not None:
                return found
        for reader in (_fluoview, _olympus_sis):  # these read the file itself
            try:
                found = reader(image)
            except errors:
                found = None
            if found is not None:
                return found
    return _sidecar(path)


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


def _nikon(tags, width):
    """NIS-Elements: tag 65331 holds CLx Lite records; dCalibration is a
    double (type 6, name length 13), bCalibrated a bool (type 1, 12)."""
    meta = tags.get(65331)
    if not isinstance(meta, bytes):
        return None
    flag = b"\x01\x0c" + "bCalibrated\0".encode("utf-16-le")
    at = meta.find(flag)
    if at >= 0 and meta[at + len(flag)] == 0:
        return None  # NIS-Elements says: not calibrated
    key = b"\x06\x0d" + "dCalibration\0".encode("utf-16-le")
    at = meta.find(key)
    if at < 0:
        return None
    um = struct.unpack_from("<d", meta, at + len(key))[0]
    if not um > 0:
        return None
    return Calibration(um * 1e-6, um * 1e-6, "Nikon NIS-Elements")


def _leica_las_x(tags, width):
    text = _text(tags, TAG_DESCRIPTION) or ""
    if not text.startswith("<LMSIOManager") or int(tags.get(TAG_RESUNIT, 0)) != 3:
        return None
    return Calibration(
        0.01 / float(tags[TAG_XRES]), 0.01 / float(tags[TAG_YRES]), "Leica LAS X"
    )


def _leica_tcs(tags, width):
    text = _text(tags, TAG_DESCRIPTION) or ""
    if not text.startswith("[Parameter-Settings]"):
        return None
    found = {}
    for line in text.splitlines():
        match = re.match(
            r"\s*(Voxel-Width|Voxel-Height)\s*\[(.+?)\]\s*=\s*([0-9.eE+-]+)", line
        )
        if match:
            unit = metres_per_unit(match.group(2))
            if unit:
                found[match.group(1)] = float(match.group(3)) * unit
    if "Voxel-Width" not in found:
        return None
    return Calibration(
        found["Voxel-Width"],
        found.get("Voxel-Height", found["Voxel-Width"]),
        "Leica TCS",
    )


def _hamamatsu_ndpi(tags, width):
    if (_text(tags, TAG_MAKE) or "").strip() != "Hamamatsu" or 65420 not in tags:
        return None
    if int(tags.get(TAG_RESUNIT, 0)) != 3:
        return None
    return Calibration(
        0.01 / float(tags[TAG_XRES]), 0.01 / float(tags[TAG_YRES]), "Hamamatsu NDPI"
    )


def _fluoview(image):
    """FluoView MM_Header (tag 34361): 10 dimension records of 100 bytes
    from byte 284: name (16), size (int32), origin, resolution (doubles),
    unit (64, Latin-1)."""
    raw = image.tag_v2.get(34361)
    if isinstance(raw, tuple):
        raw = bytes(raw)
    if not isinstance(raw, bytes) or len(raw) < 284 + 1000:
        return None
    order = "<" if image.tag_v2._endian == "<" else ">"
    found = {}
    for i in range(10):
        base = 284 + 100 * i
        name = raw[base : base + 16].split(b"\0")[0].decode("latin-1").strip().upper()
        _size, _origin, step = struct.unpack_from(order + "idd", raw, base + 16)
        unit = metres_per_unit(
            raw[base + 36 : base + 100].split(b"\0")[0].decode("latin-1").strip()
        )
        if name in ("X", "Y") and unit and step > 0:
            found[name] = step * unit
    if "X" not in found:
        return None
    return Calibration(found["X"], found.get("Y", found["X"]), "FluoView")


def _olympus_sis(image):
    """Olympus SIS (tag 33560): an offset to a 'SIS0' header (60 bytes,
    entry count at 58), entries '<hhI' (type, count, offset); type 1 is
    the general data: exponent int16 at +10, x and y calibration doubles
    at +12 and +20, little-endian. Read as tifffile's read_sis does."""
    for page in range(getattr(image, "n_frames", 1)):
        image.seek(page)
        offset = image.tag_v2.get(33560)
        if isinstance(offset, tuple):
            offset = offset[0]
        if not isinstance(offset, int):
            continue
        fp = image.fp
        fp.seek(offset)
        head = fp.read(60)
        if head[:4] != b"SIS0":
            continue
        count = struct.unpack_from("<H", head, 58)[0]
        fp.seek(offset + 60)
        entries = fp.read(8 * count)
        for i in range(count):
            kind, _n, at = struct.unpack_from("<hhI", entries, 8 * i)
            if kind != 1:
                continue
            fp.seek(at)
            block = fp.read(112)
            exponent, x, y = struct.unpack_from("<hdd", block, 10)
            if not -12 <= exponent <= 12 or not (x > 0 and y > 0):
                return None
            return Calibration(x * 10.0**exponent, y * 10.0**exponent, "Olympus SIS")
    return None


def _sidecar(path):
    """Zeiss ZEN: <image>_metadata.xml next to the image, with
    Scaling/Items/Distance Id=X/Y Value in metres."""
    if not path:
        return None
    for name in (path + "_metadata.xml", os.path.splitext(path)[0] + "_metadata.xml"):
        if not os.path.isfile(name):
            continue
        try:
            root = ET.parse(name).getroot()
        except (ET.ParseError, OSError):
            continue
        sizes = {}
        for distance in root.iter("Distance"):
            value = distance.findtext("Value")
            if distance.get("Id") in ("X", "Y") and value:
                sizes[distance.get("Id")] = float(value)
        if sizes.get("X", 0) > 0:
            return Calibration(
                sizes["X"], sizes.get("Y", sizes["X"]), "Zeiss ZEN (metadata file)"
            )
    return None
