# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Tests for scalebar.py, run through inkex like Inkscape runs it. Needs
inkex 1.4 (pip install --no-deps inkex==1.4.0, plus lxml, numpy, pillow,
tinycss2, cssselect, pyparsing, packaging).

Bar lengths are checked against values worked out here by hand from the
known pixel sizes, not with the extension's own geometry code.
"""

import base64
import io
import os
import sys

import numpy as np
import pytest
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import inkex
from test_calibration import data

from scalebar import ATTR_FOR, ATTR_SIZE, ScaleBar, nice_length

SVG = """<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
 width="300" height="200" viewBox="0 0 300 200">{body}</svg>"""


def data_uri(raw, mime="image/tiff"):
    return f"data:{mime};base64," + base64.b64encode(raw).decode()


def png(size=(200, 100), value=0, mode="L"):
    out = io.BytesIO()
    Image.fromarray(np.full(size[::-1], value, np.uint8), mode).save(out, "PNG")
    return out.getvalue()


@pytest.fixture(autouse=True)
def document_path(tmp_path, monkeypatch):
    """Inkscape tells extensions where the drawing is saved."""
    monkeypatch.setenv("DOCUMENT_PATH", str(tmp_path / "in.svg"))


def run(tmp_path, body, *args, name="in.svg"):
    """Run the extension; returns the new document, or None if inkex wrote
    nothing (it does not when the document is unchanged)."""
    path = tmp_path / name
    path.write_text(SVG.format(body=body))
    out = io.BytesIO()
    ScaleBar().run([*args, str(path)], output=out)
    if not out.getvalue():
        return None
    return inkex.load_svg(io.BytesIO(out.getvalue())).getroot()


def bars(svg):
    return svg.xpath(f"//svg:g[@{ATTR_FOR}]")


def bar_rect(group):
    rects = [r for r in group if isinstance(r, inkex.Rectangle)]
    return rects[-1]  # the bar is drawn after the optional background box


def test_nice_length():
    assert nice_length(2.29e-6) == pytest.approx(2e-6)
    assert nice_length(345e-6) == pytest.approx(200e-6)
    assert nice_length(0.7) == pytest.approx(0.5)
    assert nice_length(1.0) == pytest.approx(1.0)


def test_imagej_embedded(tmp_path):
    # 68 x 68 pixels of 0.16867 µm, drawn 136 units wide: 2 units per pixel
    body = f'<image id="im" x="10" y="20" width="136" height="136" xlink:href="{data_uri(data("imagej.tif"))}"/>'
    svg = run(tmp_path, body, "--id=im")
    (group,) = bars(svg)
    # auto: a fifth of 68 * 0.16867 µm = 2.29 µm, so 2 µm
    assert group.label == "Scale bar 2 µm"
    rect = bar_rect(group)
    assert float(rect.get("width")) == pytest.approx(2 / 0.168675 * 2, rel=1e-4)
    # bottom right: right edge at x + width - 4 % margin
    assert float(rect.get("x")) + float(rect.get("width")) == pytest.approx(
        10 + 136 - 0.04 * 136
    )
    text = group.xpath("svg:text")[0]
    assert text.text == "2 µm"


def test_fei_linked_file(tmp_path):
    tif = tmp_path / "fei.tif"
    tif.write_bytes(data("fei-helios.zip", "FEI-Helios-Ebeam-8bits.tif"))
    # 512 x 471 pixels of 3.3724 µm, drawn 256 units wide
    body = '<image id="im" width="256" height="235.5" xlink:href="fei.tif"/>'
    svg = run(tmp_path, body, "--id=im", "--length=500 µm")
    rect = bar_rect(bars(svg)[0])
    assert float(rect.get("width")) == pytest.approx(500 / 3.3724 * 0.5, rel=1e-4)


def test_preserve_aspect_ratio_meet(tmp_path):
    # a 200 x 100 raster in a 200 x 200 box: drawn 200 x 100, centred
    raw = png((200, 100))
    body = f'<image id="im" width="200" height="200" xlink:href="{data_uri(raw, "image/png")}"/>'
    svg = run(
        tmp_path,
        body,
        "--id=im",
        "--source=manual",
        "--pixel_size=1 µm",
        "--length=50 µm",
    )
    rect = bar_rect(bars(svg)[0])
    assert float(rect.get("width")) == pytest.approx(50)
    # bottom of the drawn raster is at y = 150, not 200
    bottom = float(rect.get("y")) + float(rect.get("height"))
    assert bottom == pytest.approx(150 - 0.04 * 200)


def test_manual_is_stored_and_reused(tmp_path):
    raw = png()
    body = f'<image id="im" width="100" height="50" xlink:href="{data_uri(raw, "image/png")}"/>'
    svg = run(tmp_path, body, "--id=im", "--source=manual", "--pixel_size=250 nm")
    image = svg.getElementById("im")
    assert image.get(ATTR_SIZE).split() == ["2.5e-07", "2.5e-07"]
    # run again on the result with the default source: uses the stored size
    (tmp_path / "again.svg").write_bytes(svg.tostring())
    out = io.BytesIO()
    ScaleBar().run(
        ["--id=im", "--length=10 µm", str(tmp_path / "again.svg")], output=out
    )
    again = inkex.load_svg(io.BytesIO(out.getvalue())).getroot()
    groups = bars(again)
    assert len(groups) == 1  # the earlier bar was replaced
    # 10 µm / 0.25 µm = 40 pixels, at 0.5 units per pixel
    assert float(bar_rect(groups[0]).get("width")) == pytest.approx(20)


def test_line_calibration(tmp_path):
    # 200 pixels drawn 400 units wide (2 units per pixel), in a moved and
    # scaled group; the line spans 100 pixels = 50 µm, so 0.5 µm per pixel
    raw = png((200, 100))
    body = (
        '<g transform="translate(30 40) scale(0.5)">'
        f'<image id="im" width="400" height="200" xlink:href="{data_uri(raw, "image/png")}"/>'
        "</g>"
        # 100 units in the document = 200 in the image = 100 pixels
        '<path id="ln" d="M 40 60 L 140 60"/>'
    )
    svg = run(
        tmp_path,
        body,
        "--id=im",
        "--id=ln",
        "--source=line",
        "--line_length=50 µm",
        "--length=20 µm",
    )
    image = svg.getElementById("im")
    assert float(image.get(ATTR_SIZE).split()[0]) == pytest.approx(0.5e-6)
    # 20 µm = 40 pixels = 80 units in the image's own coordinates
    assert float(bar_rect(bars(svg)[0]).get("width")) == pytest.approx(80)


def test_transformed_image_bar_follows(tmp_path):
    raw = png()
    body = (
        f'<image id="im" width="200" height="100" transform="rotate(30) translate(5 5)" '
        f'xlink:href="{data_uri(raw, "image/png")}"/>'
    )
    svg = run(tmp_path, body, "--id=im", "--source=manual", "--pixel_size=1 µm")
    group = bars(svg)[0]
    assert group.transform == svg.getElementById("im").transform
    assert group.getprevious().get("id") == "im"  # drawn right above the image


def test_auto_colour(tmp_path):
    dark = data_uri(png(value=10), "image/png")
    light = data_uri(png(value=240), "image/png")
    body = (
        f'<image id="a" width="100" height="50" xlink:href="{dark}"/>'
        f'<image id="b" y="60" width="100" height="50" xlink:href="{light}"/>'
    )
    svg = run(
        tmp_path, body, "--id=a", "--id=b", "--source=manual", "--pixel_size=1 µm"
    )
    colours = {g.get(ATTR_FOR): bar_rect(g).style.get("fill") for g in bars(svg)}
    assert colours == {"a": "#ffffff", "b": "#000000"}


def test_uncalibrated_image_reports(tmp_path, capsys):
    body = f'<image id="im" width="100" height="50" xlink:href="{data_uri(png(), "image/png")}"/>'
    assert run(tmp_path, body, "--id=im") is None  # nothing drawn
    assert "No pixel size found for: im" in capsys.readouterr().err


def test_nothing_selected_means_every_image(tmp_path):
    raw = data_uri(png(), "image/png")
    body = (
        f'<image id="a" width="100" height="50" xlink:href="{raw}"/>'
        f'<g><image id="b" y="60" width="100" height="50" xlink:href="{raw}"/></g>'
    )
    svg = run(tmp_path, body, "--source=manual", "--pixel_size=1 µm")
    assert sorted(g.get(ATTR_FOR) for g in bars(svg)) == ["a", "b"]


def test_no_images_at_all(tmp_path):
    with pytest.raises(SystemExit):
        run(tmp_path, "<rect width='5' height='5'/>")


def test_cropped_image_bar_in_the_part_that_shows(tmp_path):
    # 200 x 100 pixels drawn 200 x 100, clipped to x 20..120, y 10..60
    raw = data_uri(png(), "image/png")
    body = (
        '<defs><clipPath id="crop"><rect x="20" y="10" width="100" height="50"/></clipPath></defs>'
        f'<image id="im" width="200" height="100" clip-path="url(#crop)" xlink:href="{raw}"/>'
    )
    svg = run(tmp_path, body, "--id=im", "--source=manual", "--pixel_size=1 µm")
    rect = bar_rect(bars(svg)[0])
    # a fifth of the 100 pixels that show: 20 µm = 20 units; the margin is
    # 4 % of the visible width
    assert float(rect.get("width")) == pytest.approx(20)
    assert float(rect.get("x")) + 20 == pytest.approx(120 - 4)
    assert float(rect.get("y")) + float(rect.get("height")) == pytest.approx(60 - 4)


def test_length_text_stays_inside_the_image(tmp_path):
    # a 1-unit bar in the corner with 20-unit text: centred over the bar,
    # "1 µm" (estimated 0.6 em per character) would run past the edge
    raw = data_uri(png((100, 50)), "image/png")
    body = f'<image id="im" width="100" height="50" xlink:href="{raw}"/>'
    svg = run(
        tmp_path,
        body,
        "--id=im",
        "--source=manual",
        "--pixel_size=1 µm",
        "--length=1 µm",
        "--font_size=20",
    )
    text = bars(svg)[0].findone("svg:text")
    half = 0.3 * 20 * len("1 µm")
    assert float(text.get("x")) == pytest.approx(100 - 4 - half)
