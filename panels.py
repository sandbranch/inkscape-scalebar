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
Lay out microscope images as a figure: rows that exactly fill a given
width (each image keeps its proportions), panel letters, and scale bars
of one and the same length on every calibrated panel.

Images are moved by their transform, so a cropped (clipped) image moves
with its clip, and a scale bar already drawn on it moves along.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import inkex
from inkex.localization import inkex_gettext as _

import calibration
from scalebar import ATTR_FOR, ScaleBar, drawn_area, nice_length, visible_area

ATTR_LABEL_FOR = "data-panel-label-for"


def letters(count, style):
    out = []
    for i in range(count):
        text, n = "", i
        while True:  # A..Z, AA, AB, ...
            text = chr(ord("A") + n % 26) + text
            n = n // 26 - 1
            if n < 0:
                break
        if style.startswith("lower"):
            text = text.lower()
        if style.endswith("paren"):
            text = f"({text})"
        out.append(text)
    return out


def rows_of(boxes, columns):
    return [boxes[i : i + columns] for i in range(0, len(boxes), columns)]


class FigurePanels(ScaleBar):
    """Arrange the selected images as figure panels"""

    def add_arguments(self, pars):
        super().add_arguments(pars)
        pars.add_argument("--width", type=float, default=180.0, help="figure width, mm")
        pars.add_argument("--columns", type=int, default=2)
        pars.add_argument("--gap", type=float, default=2.0, help="mm")
        pars.add_argument("--order", default="reading", help="reading or selection")
        pars.add_argument(
            "--labels",
            default="upper",
            help="none, upper, lower, upper-paren, lower-paren",
        )
        pars.add_argument("--label_size", type=float, default=10.0, help="pt")
        pars.add_argument("--label_color", default="auto")
        pars.add_argument("--scalebars", type=inkex.Boolean, default=True)

    # -- geometry in document user units

    def doc_box(self, node):
        return node.bounding_box(node.getparent().composed_transform())

    def place(self, node, box, x, y, scale):
        """Move and scale `node` so its document box `box` lands at (x, y)
        scaled by `scale`; returns the transform applied, in the node's
        parent's coordinates."""
        move = (
            inkex.Transform(translate=(x, y))
            @ inkex.Transform(scale=scale)
            @ inkex.Transform(translate=(-box.left, -box.top))
        )
        parent = node.getparent().composed_transform()
        local = -parent @ move @ parent
        node.transform = local @ node.transform
        return local

    def mm(self, value):
        return self.svg.viewport_to_unit(f"{value}mm")  # unittouu ignores the viewBox

    def effect(self):
        images = [n for n in self.svg.selection.values() if isinstance(n, inkex.Image)]
        if not images:
            images = list(self.svg.descendants().filter(inkex.Image))
        if not images:
            raise inkex.AbortExtension(_("Select the images to arrange."))
        boxes = [(image, self.doc_box(image)) for image in images]
        boxes = [
            (i, b) for i, b in boxes if b is not None and b.width > 0 and b.height > 0
        ]
        if self.options.order == "reading":
            # rows of the current layout first (by centre, within half a
            # median height), then left to right
            tol = sorted(b.height for _, b in boxes)[len(boxes) // 2] / 2
            boxes.sort(key=lambda ib: (round(ib[1].center.y / tol), ib[1].center.x))

        width = self.mm(self.options.width)
        gap = self.mm(self.options.gap)
        label_size = self.svg.viewport_to_unit(f"{self.options.label_size}pt")
        top = min(b.top for _, b in boxes)
        left = min(b.left for _, b in boxes)

        y = top
        moved = {}
        columns = max(1, self.options.columns)
        for row in rows_of(boxes, columns):
            # one height for the row, so that the row fills the width
            ratios = [b.width / b.height for _, b in row]
            slots = max(len(row), columns)
            mean = sum(ratios) / len(ratios)
            total = sum(ratios) + mean * (
                slots - len(row)
            )  # a short last row keeps the size
            height = (width - gap * (slots - 1)) / total
            x = left
            for (image, box), ratio in zip(row, ratios):
                scale = height / box.height
                moved[image.get("id")] = self.place(image, box, x, y, scale)
                x += ratio * height + gap
            y += height + gap

        # scale bars already drawn on these images move with them
        for group in self.svg.xpath(f"//svg:g[@{ATTR_FOR}]"):
            delta = moved.get(group.get(ATTR_FOR))
            if delta is not None:
                group.transform = delta @ group.transform

        ordered = [image for image, _ in boxes]
        if self.options.labels != "none":
            self.add_labels(ordered, label_size)
        if self.options.scalebars:
            self.add_scalebars(ordered)

    # -- labels

    def add_labels(self, images, size):
        for old in self.svg.xpath(f"//svg:text[@{ATTR_LABEL_FOR}]"):
            old.getparent().remove(old)
        for image, text in zip(images, letters(len(images), self.options.labels)):
            box = self.doc_box(image)
            pad = size * 0.3
            label = inkex.TextElement()
            label.text = text
            label.set(ATTR_LABEL_FOR, image.get("id"))
            label.set("x", f"{box.left + pad:.6g}")
            label.set("y", f"{box.top + pad + size * 0.8:.6g}")
            colour = self.options.label_color
            if colour == "auto":
                colour = self.corner_colour(image)
            label.style = {
                "font-size": f"{size:.6g}px",
                "font-family": self.options.font_family,
                "font-weight": "bold",
                "fill": colour,
            }
            # in the document's root coordinates: put it in the image's
            # layer, undoing that layer's transform
            parent = image.getparent()
            label.transform = -parent.composed_transform()
            image.addnext(label)

    def corner_colour(self, image):
        data = self.image_bytes(image)
        if data is None:
            return "#000000"
        try:
            import io

            from PIL import Image

            with Image.open(io.BytesIO(data)) as im:
                w, h = im.size
        except (OSError, ValueError):
            return "#000000"
        # the top left eighth of the part that shows
        full = drawn_area(image, w, h)
        vx, vy, vw, vh = visible_area(image, full)
        x0, y0 = int((vx - full[0]) * w / full[2]), int((vy - full[1]) * h / full[3])
        dx, dy = int(vw * w / full[2]) // 8, int(vh * h / full[3]) // 8
        return self.bar_color(data, (w, h), (x0, y0, x0 + max(1, dx), y0 + max(1, dy)))

    # -- scale bars of one length

    def add_scalebars(self, images):
        found = []
        for image in images:
            data = self.image_bytes(image)
            if data is None:
                continue
            try:
                import io

                from PIL import Image

                with Image.open(io.BytesIO(data)) as im:
                    raster = im.size
            except (OSError, ValueError):
                continue
            area = drawn_area(image, *raster)
            cal = self.stored_calibration(image) or calibration.read(
                data, path=self.image_paths.get(image.get("id"))
            )
            if cal is not None:
                found.append((image, data, raster, area, cal))
        if not found:
            return
        # one length for all, about a fifth of the narrowest panel (the
        # part that shows, for a cropped one); but
        # when the fields of view differ more than tenfold, one length
        # cannot suit them all, so each panel gets its own
        fields = [
            visible_area(image, area)[2] / area[2] * raster[0] * cal.x
            for image, _, raster, area, cal in found
        ]
        if max(fields) / min(fields) > 10:
            self.options.length = "auto"
            inkex.errormsg(
                _(
                    "The panels' magnifications differ more than tenfold, so each "
                    "panel got a scale bar of its own length."
                )
            )
        else:
            length = nice_length(0.2 * min(fields))
            self.options.length = f"{length / 1e-6:.10g} µm"
        for image, data, raster, area, cal in found:
            self.draw(image, cal, data, raster, area)
        missing = [
            image.get("id") for image in images if image not in [f[0] for f in found]
        ]
        if missing:
            inkex.errormsg(
                _("No scale bar (no pixel size found) on: {}").format(
                    ", ".join(missing)
                )
            )


if __name__ == "__main__":
    FigurePanels().run()
