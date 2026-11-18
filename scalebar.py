#!/usr/bin/env python3
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
Draw a calibrated scale bar on microscope images.

The pixel size comes from the image file (OME-TIFF, ImageJ/Fiji, Thermo
Fisher/FEI, Zeiss SEM, DigitalMicrograph, JEOL SightX; see
calibration.py), from a pixel size typed in, or from a line drawn along
a known length in the image (a burnt-in scale bar, a grid). A typed or
measured calibration is stored on the image, so running the extension
again (after resizing the image, say) needs no input.
"""

import base64
import io
import math
import os
import re
from urllib.parse import unquote, urlparse

import inkex
import numpy as np
from inkex.localization import inkex_gettext as _
from PIL import Image

import calibration

ATTR_SIZE = "data-pixel-size-m"  # stored calibration, metres per pixel (x y)
ATTR_SOURCE = "data-pixel-size-source"
ATTR_FOR = "data-scalebar-for"  # on a scale bar group: the image's id


def nice_length(target):
    """The largest 1, 2 or 5 times a power of ten that is <= target."""
    exponent = math.floor(math.log10(target))
    for step in (5, 2, 1):
        value = step * 10**exponent
        if value <= target * (1 + 1e-9):
            return value
    return 10 ** (exponent - 1) * 5


def drawn_area(image, raster_w, raster_h):
    """(x, y, width, height) of the raster inside the image box, in the
    image's user units, following preserveAspectRatio."""
    x = image.to_dimensionless(image.get("x", "0"))
    y = image.to_dimensionless(image.get("y", "0"))
    width = image.to_dimensionless(image.get("width", str(raster_w)))
    height = image.to_dimensionless(image.get("height", str(raster_h)))
    aspect = (image.get("preserveAspectRatio") or "xMidYMid meet").split()
    if aspect[0] == "none":
        return x, y, width, height
    scale = min(width / raster_w, height / raster_h)
    if len(aspect) > 1 and aspect[1] == "slice":
        scale = max(width / raster_w, height / raster_h)
    dw, dh = raster_w * scale, raster_h * scale
    align = aspect[0]
    fx = {"xMin": 0.0, "xMid": 0.5, "xMax": 1.0}.get(align[:4], 0.5)
    fy = {"YMin": 0.0, "YMid": 0.5, "YMax": 1.0}.get(align[4:], 0.5)
    return x + (width - dw) * fx, y + (height - dh) * fy, dw, dh


def visible_area(image, area):
    """`area` (from drawn_area) cut down to the image's clip, for a
    cropped image, so that the scale bar sits in the part that shows."""
    x, y, width, height = area
    clip = image.clip
    if clip is None or clip.get("clipPathUnits") == "objectBoundingBox":
        return area
    box = clip.bounding_box()
    if box is None:
        return area
    left, top = max(x, box.left), max(y, box.top)
    right, bottom = min(x + width, box.right), min(y + height, box.bottom)
    if right <= left or bottom <= top:
        return area
    return left, top, right - left, bottom - top


class ScaleBar(inkex.EffectExtension):
    """Draw a calibrated scale bar on the selected microscope images"""

    def __init__(self):
        super().__init__()
        self.image_paths = {}  # image id -> linked file, for sidecar metadata

    def add_arguments(self, pars):
        pars.add_argument("--tab")
        pars.add_argument("--source", default="auto", help="auto, manual or line")
        pars.add_argument("--pixel_size", default="", help="manual: e.g. 0.325 µm")
        pars.add_argument("--line_length", default="", help="line: e.g. 10 µm")
        pars.add_argument("--length", default="auto", help="auto, or e.g. 20 µm")
        pars.add_argument("--position", default="bottom-right")
        pars.add_argument(
            "--margin", type=float, default=4.0, help="percent of the image width"
        )
        pars.add_argument(
            "--thickness", type=float, default=1.2, help="percent of the image width"
        )
        pars.add_argument("--color", default="auto", help="auto, white or black")
        pars.add_argument("--label", type=inkex.Boolean, default=True)
        pars.add_argument(
            "--font_size", type=float, default=4.0, help="percent of the image width"
        )
        pars.add_argument("--font_family", default="sans-serif")
        pars.add_argument("--box", default="none", help="none, dark or light")

    # -- the image's pixels and calibration

    def image_bytes(self, image):
        href = image.get("xlink:href") or image.get("href") or ""
        if href.startswith("data:"):
            header, _comma, payload = href.partition(",")
            if ";base64" in header:
                return base64.b64decode(re.sub(r"\s+", "", payload))
            return unquote(payload).encode("latin-1")
        candidates = []
        if href:
            path = unquote(urlparse(href).path) if href.startswith("file:") else href
            candidates.append(path)
            if not os.path.isabs(path):
                folder = self.svg_path()
                if folder:
                    candidates.append(os.path.join(folder, path))
        absref = image.get("sodipodi:absref")
        if absref:
            candidates.append(absref)
        for path in candidates:
            if os.path.isfile(path):
                with open(path, "rb") as f:
                    self.image_paths[image.get("id")] = path
                    return f.read()
        return None

    def stored_calibration(self, image):
        value = image.get(ATTR_SIZE)
        if not value:
            return None
        try:
            parts = [float(v) for v in value.split()]
            return calibration.Calibration(
                parts[0], parts[-1], image.get(ATTR_SOURCE) or _("stored")
            )
        except (ValueError, IndexError):
            return None

    def store(self, image, cal):
        image.set(ATTR_SIZE, f"{cal.x:.10g} {cal.y:.10g}")
        image.set(ATTR_SOURCE, cal.source)

    def line_calibration(self, image, line, raster, area):
        """Pixel size from a line drawn along a known length."""
        known = calibration.parse_length(self.options.line_length)
        points = list(line.path.to_absolute().end_points)
        if len(points) < 2:
            raise inkex.AbortExtension(_("The calibration line needs two points."))
        # line coordinates -> document -> the image's user space
        to_doc = line.getparent().composed_transform() @ line.transform
        to_image = -(image.getparent().composed_transform() @ image.transform)
        first = to_image.apply_to_point(to_doc.apply_to_point(points[0]))
        last = to_image.apply_to_point(to_doc.apply_to_point(points[-1]))
        _x, _y, width, height = area
        dx = (last.x - first.x) * raster[0] / width
        dy = (last.y - first.y) * raster[1] / height
        pixels = math.hypot(dx, dy)
        if pixels <= 0:
            raise inkex.AbortExtension(_("The calibration line has no length."))
        size = known / pixels
        return calibration.Calibration(
            size, size, _("line of {}").format(self.options.line_length.strip())
        )

    def calibrate(self, image, data, raster, area, line):
        source = self.options.source
        if source == "manual":
            size = calibration.parse_length(self.options.pixel_size)
            cal = calibration.Calibration(size, size, _("typed in"))
            self.store(image, cal)
            return cal
        if source == "line":
            if line is None:
                raise inkex.AbortExtension(
                    _("Select the image and a line drawn along a known length.")
                )
            cal = self.line_calibration(image, line, raster, area)
            self.store(image, cal)
            return cal
        return self.stored_calibration(image) or (
            calibration.read(data, path=self.image_paths.get(image.get("id")))
            if data
            else None
        )

    # -- drawing

    def bar_color(self, data, raster, box):
        """White on dark ground, black on light ground."""
        if self.options.color in ("white", "black"):
            return "#ffffff" if self.options.color == "white" else "#000000"
        if data is None:
            return "#ffffff"
        try:
            with Image.open(io.BytesIO(data)) as im:
                pixels = np.asarray(im)
        except (OSError, ValueError):
            return "#ffffff"
        x0, y0, x1, y1 = box  # in raster pixels
        patch = pixels[max(0, y0) : max(y0 + 1, y1), max(0, x0) : max(x0 + 1, x1)]
        if patch.size == 0:
            return "#ffffff"
        patch = patch.astype(float)
        if patch.ndim == 3:
            patch = patch[..., :3].mean(axis=-1)
        if np.issubdtype(pixels.dtype, np.integer):
            top = float(np.iinfo(pixels.dtype).max)
        else:
            top = float(pixels.max()) or 1.0
        return "#000000" if patch.mean() / top > 0.5 else "#ffffff"

    def draw(self, image, cal, data, raster, area):
        full_x, full_y, full_w, full_h = area
        uu_per_px = full_w / raster[0]
        # placed and sized within the part that shows (a cropped image)
        x, y, width, height = visible_area(image, area)
        if self.options.length.strip().lower() in ("", "auto"):
            length = nice_length(0.2 * width / uu_per_px * cal.x)
        else:
            length = calibration.parse_length(self.options.length)
        bar_w = length / cal.x * uu_per_px
        margin = width * self.options.margin / 100
        thick = width * self.options.thickness / 100
        font = width * self.options.font_size / 100 if self.options.label else 0
        gap = font * 0.25
        block_h = thick + (font * 1.1 + gap if self.options.label else 0)

        position = self.options.position
        left = x + margin if "left" in position else x + width - margin - bar_w
        top = y + margin if "top" in position else y + height - margin - block_h
        bar_y = top + block_h - thick

        group = inkex.Group()
        group.set("id", self.svg.get_unique_id("scalebar"))
        group.set(ATTR_FOR, image.get("id"))
        group.label = _("Scale bar {}").format(calibration.format_length(length, 3))
        if image.transform:
            group.transform = image.transform

        # sample the ground under the bar, in raster pixels
        px_x, px_y = raster[0] / full_w, raster[1] / full_h
        pad = margin * 0.5
        box_px = (
            int((left - pad - full_x) * px_x),
            int((top - pad - full_y) * px_y),
            int((left + bar_w + pad - full_x) * px_x),
            int((bar_y + thick + pad - full_y) * px_y),
        )
        color = self.bar_color(data, raster, box_px)

        if self.options.box in ("dark", "light"):
            fill = "#000000" if self.options.box == "dark" else "#ffffff"
            color = "#ffffff" if self.options.box == "dark" else "#000000"
            label_w = max(bar_w, font * 0.6 * len(calibration.format_length(length, 3)))
            back = inkex.Rectangle.new(
                left + bar_w / 2 - label_w / 2 - pad,
                top - pad,
                label_w + 2 * pad,
                block_h + 2 * pad,
            )
            back.style = {"fill": fill, "fill-opacity": "0.6", "stroke": "none"}
            group.add(back)

        bar = inkex.Rectangle.new(left, bar_y, bar_w, thick)
        bar.style = {"fill": color, "stroke": "none"}
        group.add(bar)
        if self.options.label:
            text = inkex.TextElement()
            text.text = calibration.format_length(length, 3)
            # centred over the bar, but kept inside the image (a short bar
            # in a corner would push its text over the edge); the text
            # width is estimated at 0.6 em per character
            half = 0.3 * font * len(text.text)
            centre = left + bar_w / 2
            centre = min(max(centre, x + margin + half), x + width - margin - half)
            text.set("x", f"{centre:.6g}")
            text.set("y", f"{bar_y - gap:.6g}")
            text.style = {
                "font-size": f"{font:.6g}px",
                "font-family": self.options.font_family,
                "text-anchor": "middle",
                "fill": color,
                "stroke": "none",
            }
            group.add(text)

        # replace an earlier scale bar of this image
        for old in self.svg.xpath(f'//svg:g[@{ATTR_FOR}="{image.get("id")}"]'):
            old.getparent().remove(old)
        image.addnext(group)
        return length

    # -- the effect

    def effect(self):
        images, line = [], None
        for node in self.svg.selection.values():
            if isinstance(node, inkex.Image):
                images.append(node)
            elif isinstance(node, inkex.Group):
                images.extend(node.descendants().filter(inkex.Image))
            elif isinstance(node, (inkex.PathElement, inkex.Line, inkex.Polyline)):
                line = node
        if not self.svg.selection:
            # nothing selected: every image (this is also how the command
            # line runs it, since Inkscape passes no selection there)
            images = list(self.svg.descendants().filter(inkex.Image))
        if not images:
            raise inkex.AbortExtension(_("Select one or more images."))
        if self.options.source == "line" and len(images) != 1:
            raise inkex.AbortExtension(
                _("To calibrate with a line, select one image and the line.")
            )

        missing = []
        for image in images:
            data = self.image_bytes(image)
            raster = None
            if data is not None:
                try:
                    with Image.open(io.BytesIO(data)) as im:
                        raster = im.size
                except (OSError, ValueError):
                    raster = None
            if raster is None:
                missing.append(image.get("id"))
                continue
            area = drawn_area(image, *raster)
            try:
                cal = self.calibrate(image, data, raster, area, line)
            except ValueError as error:
                raise inkex.AbortExtension(str(error)) from error
            if cal is None:
                missing.append(image.get("id"))
                continue
            self.draw(image, cal, data, raster, area)
        if missing:
            inkex.errormsg(
                _(
                    "No pixel size found for: {}. Type one in, or calibrate with "
                    "a line along a known length (Calibration tab)."
                ).format(", ".join(missing))
            )


if __name__ == "__main__":
    ScaleBar().run()
