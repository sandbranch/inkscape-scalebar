# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Tests for calibration.py: the real instrument files in tests/data (from
RosettaSciIO's test data, see tests/data/README.md), with the pixel sizes
RosettaSciIO's own tests expect for them, plus generated files.

    python3 -m pytest tests/
"""

import gzip
import io
import os
import sys
import zipfile

import numpy as np
import pytest
from PIL import Image
from PIL.TiffImagePlugin import ImageFileDirectory_v2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import calibration

DATA = os.path.join(HERE, "data")


def data(name, member=None):
    path = os.path.join(DATA, name)
    if member:
        with zipfile.ZipFile(path) as z:
            return z.read(member)
    if name.endswith(".gz"):
        with gzip.open(path) as f:
            return f.read()
    with open(path, "rb") as f:
        return f.read()


# (file, zip member, expected x in metres, source); None: no calibration.
# Values from RosettaSciIO's rsciio/tests/test_tiff.py.
REAL_FILES = [
    ("imagej.tif", None, 0.16867e-6, "ImageJ"),
    ("imagej-no-scale.tif", None, None, None),
    ("digitalmicrograph.tif", None, 0.16867e-6, "Gatan DigitalMicrograph"),
    ("fei-helios.zip", "FEI-Helios-Ebeam-8bits.tif", 3.3724e-6, "Thermo Fisher/FEI"),
    ("fei-helios.zip", "FEI-Helios-Ebeam-16bits.tif", 3.3724e-6, "Thermo Fisher/FEI"),
    (
        "fei-helios.zip",
        "FEI-Helios-navcam.tif",
        0.2640e-3,
        "Thermo Fisher/FEI (IRBeam)",
    ),
    ("fei-helios.zip", "FEI-Helios-navcam-with-no-IRBeam.tif", None, None),
    ("zeiss-sem.zip", "test_tiff_Zeiss_SEM_1k.tif", 2.614514e-6, "Zeiss SEM"),
    ("zeiss-sem.zip", "test_tiff_Zeiss_SEM_512pix.tif", 0.011649976e-6, "Zeiss SEM"),
    ("jeol-sightx-tem-mag.tif.gz", None, 1.8208e-9, "JEOL SightX"),
    # print resolution only: deliberately not used as a calibration
    ("zeiss-axiovision.tif", None, None, None),
    ("zeiss-axiovision-rgb.tif", None, None, None),
    # other makers: values from tifffile, nd2 or the file's own sidecar
    ("olympus-sis-quemesa.tif", None, 2.392791775876109e-11, "Olympus SIS"),
    ("olympus-cellsens-sc50-crop.tif", None, 5.506001494814109e-07, "Olympus SIS"),
    ("fluoview-fv500-page0.tif", None, 1.2429611524567008e-06, "FluoView"),
    ("nikon-nis-40x-crop.tif", None, 1.625e-07, "Nikon NIS-Elements"),
    ("nikon-nis-20x-rgb-crop.tif", None, 2.4285714285714288e-07, "Nikon NIS-Elements"),
    ("leica-tcs.tif", None, 2.929688e-06, "Leica TCS"),
]


@pytest.mark.parametrize(("name", "member", "expected", "source"), REAL_FILES)
def test_real_files(name, member, expected, source):
    found = calibration.read(data(name, member))
    if expected is None:
        assert found is None
        return
    assert found.source == source
    assert found.x == pytest.approx(expected, rel=1e-4)
    assert found.y == pytest.approx(expected, rel=1e-4)


def tiff(description=None, resolution=None, extra=None, size=(40, 30)):
    """A small grey TIFF with the given tags."""
    tags = ImageFileDirectory_v2()
    if description is not None:
        tags[270] = description
    if resolution is not None:
        tags[282] = resolution
        tags[283] = resolution
        tags[296] = 1
    for tag, value in (extra or {}).items():
        tags[tag] = value
    out = io.BytesIO()
    Image.fromarray(np.zeros(size[::-1], np.uint8)).save(out, "TIFF", tiffinfo=tags)
    return out.getvalue()


OME = """<?xml version="1.0" encoding="UTF-8"?>
<OME xmlns="http://www.openmicroscopy.org/Schemas/OME/2016-06">
  <Image ID="Image:0"><Pixels ID="Pixels:0" DimensionOrder="XYCZT" Type="uint8"
    SizeX="40" SizeY="30" SizeC="1" SizeZ="1" SizeT="1" {attrs}>
    <Channel ID="Channel:0:0" SamplesPerPixel="1"/>
    <TiffData/></Pixels></Image>
</OME>"""


@pytest.mark.parametrize(
    ("attrs", "x", "y"),
    [
        (
            'PhysicalSizeX="0.325" PhysicalSizeY="0.325"',
            0.325e-6,
            0.325e-6,
        ),  # default µm
        (
            (
                'PhysicalSizeX="2.5" PhysicalSizeXUnit="nm" PhysicalSizeY="5" '
                'PhysicalSizeYUnit="nm"'
            ),
            2.5e-9,
            5e-9,
        ),
        ('PhysicalSizeX="1.2" PhysicalSizeXUnit="mm"', 1.2e-3, 1.2e-3),
    ],
)
def test_ome(attrs, x, y):
    found = calibration.read(tiff(OME.format(attrs=attrs)))
    assert found.source == "OME-TIFF"
    assert (found.x, found.y) == (pytest.approx(x), pytest.approx(y))


def test_ome_without_size():
    assert calibration.read(tiff(OME.format(attrs=""))) is None


@pytest.mark.parametrize(
    ("unit", "metres"),
    [
        (b"micron", 1e-6),
        (b"\\u00B5m", 1e-6),  # how ImageJ writes it
        (b"\xc2\xb5m", 1e-6),  # UTF-8
        (b"\xb5m", 1e-6),  # Latin-1
        (b"nm", 1e-9),
        (b"mm", 1e-3),
    ],
)
def test_imagej_units(unit, metres):
    found = calibration.read(
        tiff(b"ImageJ=1.54p\nunit=" + unit + b"\n", resolution=4.0)
    )
    assert found.x == pytest.approx(metres / 4)


def test_imagej_pixel_unit_is_not_a_calibration():
    assert calibration.read(tiff("ImageJ=1.54p\nunit=pixel\n", resolution=4.0)) is None


def test_plain_files_have_none():
    out = io.BytesIO()
    Image.new("RGB", (10, 10)).save(out, "PNG")
    assert calibration.read(out.getvalue()) is None
    assert calibration.read(tiff(resolution=300.0)) is None  # print resolution only
    assert calibration.read(b"not an image") is None


def test_fei_ini_from_text():
    text = "[User]\r\nUser=x\r\n[Scan]\r\nPixelWidth=1.5e-09\r\nPixelHeight=3e-09\r\n"
    found = calibration.read(tiff(extra={34682: text}))
    assert (found.x, found.y) == (pytest.approx(1.5e-9), pytest.approx(3e-9))


def test_lengths():
    assert calibration.format_length(2.5e-6) == "2.5 µm"
    assert calibration.format_length(0.2640e-3) == "264 µm"
    assert calibration.parse_length("0.5 µm") == pytest.approx(0.5e-6)
    assert calibration.parse_length("200nm") == pytest.approx(200e-9)
    assert calibration.parse_length("3 micron") == pytest.approx(3e-6)
    with pytest.raises(ValueError):
        calibration.parse_length("3 parsecs")


def resolution_tiff(description, xres, unit, extra=None):
    tags = ImageFileDirectory_v2()
    if description is not None:
        tags[270] = description
    tags[282] = xres
    tags[283] = xres
    tags[296] = unit
    for tag, value in (extra or {}).items():
        tags[tag] = value
    out = io.BytesIO()
    Image.fromarray(np.zeros((8, 8), np.uint8)).save(out, "TIFF", tiffinfo=tags)
    return out.getvalue()


def test_leica_las_x():
    # as LAS X writes it: centimetres, numerator 2**32 - 1
    from fractions import Fraction

    xres = Fraction(4294967295, 36729)
    desc = "<LMSIOManager><ProductVersion>2,0,0,0</ProductVersion></LMSIOManager>"
    found = calibration.read(resolution_tiff(desc, xres, 3))
    assert found.source == "Leica LAS X"
    assert found.x == pytest.approx(0.01 / float(xres))
    # the same resolution in a file that is not from LAS X is not a calibration
    assert calibration.read(resolution_tiff("something else", xres, 3)) is None


def test_hamamatsu_ndpi():
    data = resolution_tiff(None, 43826.0, 3, {271: "Hamamatsu", 65420: 1})
    found = calibration.read(data)
    assert found.source == "Hamamatsu NDPI"
    assert found.x == pytest.approx(2.281750559028887e-07)
    assert (
        calibration.read(resolution_tiff(None, 43826.0, 3, {271: "Hamamatsu"})) is None
    )


def test_nikon_not_calibrated():
    key = b"\x06\x0d" + "dCalibration\0".encode("utf-16-le")
    off = b"\x01\x0c" + "bCalibrated\0".encode("utf-16-le")
    import struct

    calibrated = key + struct.pack("<d", 0.5) + off + b"\x01"
    found = calibration.read(tiff(extra={65331: calibrated}))
    assert found.x == pytest.approx(0.5e-6)
    assert (
        calibration.read(
            tiff(extra={65331: key + struct.pack("<d", 0.5) + off + b"\x00"})
        )
        is None
    )


def test_zeiss_zen_metadata_file(tmp_path):
    image = tmp_path / "cells.tiff"
    image.write_bytes(tiff(resolution=300.0))  # print resolution only
    (tmp_path / "cells.tiff_metadata.xml").write_text(
        "<ImageMetadata><Scaling><Items>"
        '<Distance Id="X"><Value>1.0833333333333332E-07</Value></Distance>'
        '<Distance Id="Y"><Value>1.0833333333333332E-07</Value></Distance>'
        "</Items></Scaling></ImageMetadata>"
    )
    found = calibration.read(str(image))
    assert found.source == "Zeiss ZEN (metadata file)"
    assert found.x == pytest.approx(1.0833333333333332e-07)
    # from the bytes, with the path given
    assert calibration.read(image.read_bytes(), path=str(image)).x == found.x
    assert calibration.read(image.read_bytes()) is None
