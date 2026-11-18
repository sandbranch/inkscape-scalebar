# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later
# Used to make the small test files in tests/data from large samples.
"""Shrink a single-IFD, strip-organised classic TIFF whose pixel strips come
before all metadata, by keeping only the first K strips. Every metadata byte
is kept verbatim; only offsets that point past the cut, ImageLength and the
strip counts change. Handles nested offsets for EXIF (34665) and Olympus SIS
(33560). Usage: crop_strips.py IN OUT K"""

import struct
import sys

TYPE_SIZE = {
    1: 1,
    2: 1,
    3: 2,
    4: 4,
    5: 8,
    6: 1,
    7: 1,
    8: 2,
    9: 4,
    10: 8,
    11: 4,
    12: 8,
    13: 4,
    16: 8,
    17: 8,
    18: 8,
}

src, dst, keep = sys.argv[1], sys.argv[2], int(sys.argv[3])
with open(src, "rb") as f:
    data = bytearray(f.read())
bo = "<" if data[:2] == b"II" else ">"
u16 = lambda o: struct.unpack_from(bo + "H", data, o)[0]
u32 = lambda o: struct.unpack_from(bo + "I", data, o)[0]


def entries(ifd):
    n = u16(ifd)
    for i in range(n):
        e = ifd + 2 + 12 * i
        code, typ, cnt = struct.unpack_from(bo + "HHI", data, e)
        yield e, code, typ, cnt


ifd0 = u32(4)
tags = {code: (e, typ, cnt) for e, code, typ, cnt in entries(ifd0)}
assert u32(ifd0 + 2 + 12 * u16(ifd0)) == 0, "only single-IFD files"


def array(code):
    e, typ, cnt = tags[code]
    size = TYPE_SIZE[typ]
    fmt = bo + {2: "H", 4: "I"}[size] * cnt
    where = e + 8 if size * cnt <= 4 else u32(e + 8)
    return list(struct.unpack_from(fmt, data, where))


offsets, counts = array(273), array(279)
rows_per_strip = u16(tags[278][0] + 8) if tags[278][1] == 3 else u32(tags[278][0] + 8)
pix_start, pix_end = offsets[0], offsets[-1] + counts[-1]
assert offsets == sorted(offsets) and all(
    offsets[i] + counts[i] == offsets[i + 1] for i in range(len(offsets) - 1)
), "strips not contiguous"
assert ifd0 >= pix_end, "metadata must follow the pixel data"
cut = offsets[keep - 1] + counts[keep - 1]
delta = pix_end - cut


def shift(o):
    v = u32(o)
    if v >= pix_end:
        struct.pack_into(bo + "I", data, o, v - delta)


def fix_ifd(ifd, top):
    for e, code, typ, cnt in list(entries(ifd)):
        if TYPE_SIZE.get(typ, 1) * cnt > 4:
            shift(e + 8)
        if code in (34665, 34853, 40965) and typ in (
            4,
            13,
        ):  # sub-IFDs: EXIF, GPS, interop
            sub = u32(e + 8)
            if sub >= pix_end:
                fix_ifd(sub, False)
                shift(e + 8)
        if top and code == 33560 and typ == 4 and cnt == 1:  # Olympus SIS block
            sis = u32(e + 8)
            if data[sis : sis + 4] == b"SIS0":
                n = struct.unpack_from("<H", data, sis + 58)[0]
                for i in range(n):
                    o = sis + 60 + 8 * i + 4
                    v = struct.unpack_from("<I", data, o)[0]
                    if v >= pix_end:
                        struct.pack_into("<I", data, o, v - delta)
            shift(e + 8)
        if top and code in (273, 279):
            struct.pack_into(bo + "I", data, e + 4, keep)
        if top and code == 257:
            rows = keep * rows_per_strip
            if typ == 3:
                struct.pack_into(bo + "H", data, e + 8, rows)
            else:
                struct.pack_into(bo + "I", data, e + 8, rows)


fix_ifd(ifd0, True)
# if strip arrays were inline before (count <= 1) nothing else to do
struct.pack_into(bo + "I", data, 4, ifd0 - delta)
out = data[:cut] + data[pix_end:]
with open(dst, "wb") as f:
    f.write(out)
print(
    f"{dst}: kept {keep} of {len(offsets)} strips, {keep * rows_per_strip} rows, {len(out)} bytes"
)
