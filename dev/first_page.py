# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later
# Used to make the small test files in tests/data from large samples.
"""Keep only the first page of a classic TIFF whose page-0 IFD and data all
lie before the second IFD: truncate there and zero IFD0's next pointer.
Usage: first_page.py IN OUT"""

import struct
import sys

with open(sys.argv[1], "rb") as f:
    data = bytearray(f.read())
bo = "<" if data[:2] == b"II" else ">"
ifd0 = struct.unpack_from(bo + "I", data, 4)[0]
n = struct.unpack_from(bo + "H", data, ifd0)[0]
nxt_at = ifd0 + 2 + 12 * n
ifd1 = struct.unpack_from(bo + "I", data, nxt_at)[0]
struct.pack_into(bo + "I", data, nxt_at, 0)
with open(sys.argv[2], "wb") as f:
    f.write(data[:ifd1])
print(sys.argv[2], ifd1, "bytes")
