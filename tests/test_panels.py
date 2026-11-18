# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Tests for panels.py (Figure Panels), run through inkex like Inkscape
runs it. Expected positions are worked out here by hand.
"""

import io
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import inkex
from test_scalebar import SVG, bar_rect, bars, data_uri, png

from panels import ATTR_LABEL_FOR, FigurePanels, letters
from scalebar import ATTR_SIZE, nice_length

MM = 96 / 25.4  # user units (px) per mm in the test document


@pytest.fixture(autouse=True)
def document_path(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCUMENT_PATH", str(tmp_path / "in.svg"))


def run(tmp_path, body, *args):
    path = tmp_path / "in.svg"
    path.write_text(SVG.format(body=body))
    out = io.BytesIO()
    FigurePanels().run([*args, str(path)], output=out)
    return inkex.load_svg(io.BytesIO(out.getvalue())).getroot()


def doc_box(svg, node_id):
    node = svg.getElementById(node_id)
    return node.bounding_box(node.getparent().composed_transform())


def two_panels(size_b):
    """A wide image, and to its right a square one in a scaled group;
    `size_b` is the pixel size of the second, in metres."""
    wide = data_uri(png((200, 100)), "image/png")
    square = data_uri(png((100, 100)), "image/png")
    return (
        f'<image id="a" x="5" y="5" width="100" height="50" {ATTR_SIZE}="1e-6" '
        f'xlink:href="{wide}"/>'
        '<g transform="translate(120 0) scale(0.5)">'
        f'<image id="b" y="10" width="120" height="120" {ATTR_SIZE}="{size_b}" '
        f'xlink:href="{square}"/></g>'
    )


def test_letters():
    assert letters(3, "upper") == ["A", "B", "C"]
    assert letters(28, "lower")[26:] == ["aa", "ab"]
    assert letters(2, "upper-paren") == ["(A)", "(B)"]


def test_row_fills_the_width(tmp_path):
    svg = run(tmp_path, two_panels(2e-6), "--width=180", "--gap=2", "--columns=2")
    a, b = doc_box(svg, "a"), doc_box(svg, "b")
    # ratios 2 and 1: height = (180 - 2) / 3 mm
    height = (180 - 2) / 3 * MM
    assert a.height == pytest.approx(height)
    assert b.height == pytest.approx(height)
    assert a.width == pytest.approx(2 * height)
    assert b.width == pytest.approx(height)
    assert (a.left, a.top) == pytest.approx((5, 5))  # the figure stays where it was
    assert b.left == pytest.approx(5 + 2 * height + 2 * MM)
    assert b.right - a.left == pytest.approx(180 * MM)
    assert b.top == pytest.approx(5)


def test_labels_in_reading_order(tmp_path):
    svg = run(tmp_path, two_panels(2e-6))
    labels = {
        t.get(ATTR_LABEL_FOR): t.text
        for t in svg.xpath(f"//svg:text[@{ATTR_LABEL_FOR}]")
    }
    assert labels == {"a": "A", "b": "B"}


def test_one_bar_length_for_all(tmp_path, capsys):
    # fields of view 200 µm and 200 µm: a fifth is 40 µm, rounded
    svg = run(tmp_path, two_panels(2e-6))
    length = nice_length(40e-6)
    groups = {g.get("data-scalebar-for"): g for g in bars(svg)}
    assert sorted(groups) == ["a", "b"]
    assert len({g.label for g in groups.values()}) == 1
    # a: 1 µm per pixel, 200 pixels drawn 100 units wide (in its own units)
    assert float(bar_rect(groups["a"]).get("width")) == pytest.approx(
        length / 1e-6 * 0.5
    )
    # b: 2 µm per pixel, 100 pixels drawn 120 units wide
    assert float(bar_rect(groups["b"]).get("width")) == pytest.approx(
        length / 2e-6 * 1.2
    )
    assert "differ" not in capsys.readouterr().err


def test_own_lengths_when_magnifications_differ(tmp_path, capsys):
    # fields of view 200 µm and 10 mm
    svg = run(tmp_path, two_panels(100e-6))
    labels = {g.get("data-scalebar-for"): g.label for g in bars(svg)}
    assert labels["a"] != labels["b"]
    assert "differ more than tenfold" in capsys.readouterr().err


def test_moving_twice_keeps_one_bar_each(tmp_path):
    svg = run(tmp_path, two_panels(2e-6))
    path = tmp_path / "again.svg"
    path.write_bytes(svg.tostring())
    out = io.BytesIO()
    FigurePanels().run(["--width=120", str(path)], output=out)
    again = inkex.load_svg(io.BytesIO(out.getvalue())).getroot()
    assert len(bars(again)) == 2
    assert len(again.xpath(f"//svg:text[@{ATTR_LABEL_FOR}]")) == 2
    assert doc_box(again, "b").right - doc_box(again, "a").left == pytest.approx(
        120 * MM
    )


def test_width_in_mm_when_user_units_are_not_px(tmp_path):
    # 2 mm per user unit: inkex's unittouu would ignore that
    path = tmp_path / "in.svg"
    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"'
        ' width="300mm" height="200mm" viewBox="0 0 150 100">'
        + two_panels(2e-6)
        + "</svg>"
    )
    out = io.BytesIO()
    FigurePanels().run(["--width=180", "--gap=2", str(path)], output=out)
    svg = inkex.load_svg(io.BytesIO(out.getvalue())).getroot()
    assert doc_box(svg, "b").right - doc_box(svg, "a").left == pytest.approx(
        90, rel=1e-5
    )
    assert doc_box(svg, "a").height == pytest.approx((180 - 2) / 3 / 2, rel=1e-5)
