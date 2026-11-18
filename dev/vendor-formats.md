# Vendor TIFF calibration: samples and Pillow recipes

Research for inkscape-scalebar (calibration.py), 2026-11-18. The repo was not
modified. Everything below was checked on real files unless marked
**unverified**.

Paths:

- Licensed samples: `/tmp/claude-1000/-home-david-store-code-sandbranch/21fddc13-858b-4af5-91d4-b622e9c8aa12/scratchpad/vendor-samples/`
- Small derived copies (vendor metadata bytes kept verbatim, pixel strips cut): `.../scratchpad/vendor-samples/derived/`
- Raw downloads, including files with unverified licences: `.../scratchpad/dl/`
- Scripts: `.../scratchpad/scripts/` (`proto_pillow.py` is a Pillow-only prototype of every recipe below; `crop_strips.py` and `first_page.py` made the derived files; `dump.py`/`probe.py`/`remote_ifd.py` are inspection helpers)
- Reference sources read: `.../scratchpad/ref/` (tifffile 2026.11.16 tests, RosettaSciIO `_api.py` and `test_tiff.py`, Bio-Formats readers, OpenSlide NDPI code)

Tools used for the independent values: tifffile 2026.11.16, nd2 0.12.0 (its CLx Lite
decoder), in a throwaway venv, run with `python -I`. The Pillow prototype was run with
Pillow 13.0.0 (venv) and 12.1.1 (system); both gave identical results.

`calibration.read()` from the current repo returns None for every new sample
below (checked), so none of these formats is misdetected today.

Bio-Formats expected values (`.bfconfig` files of the OME curated repository) were
not available: that config repository is not public as far as I could find.
**Unverified** for every file.

---

## Summary table

| file (in vendor-samples/) | size | licence | expected pixel size | source of the value |
|---|---|---|---|---|
| olympus/olympus-sis-quemesa-rsciio.tif | 101042 | GPL-3.0 (RosettaSciIO) | 2.392791775876109e-11 m | tifffile read_sis; RosettaSciIO test expects 2.3928e-11 m |
| olympus/olympus-cellsens-sc50-4x-zenodo7845067.tif | 4948990 | Zenodo "other-pd" (public domain) | 5.506001494814109e-07 m | tifffile read_sis |
| derived/olympus-cellsens-sc50-4x-crop.tif | 361470 | same, derived | 5.506001494814109e-07 m | tifffile read_sis on the derived file |
| derived/fluoview-fv500-10-31_E1-page0.tif | 542450 | CC0 (samples.scif.io) | 1.2429611524567008e-06 m | tifffile read_mm_header / series coord_scales |
| nikon/nikon-nis-40x-h3k9me3-zenodo7677827.tif | 8415436 | CC-BY-4.0 | 1.625e-07 m | nd2 CLx Lite decode of tag 65331 dCalibration (0.1625 µm); tag 65326 equal |
| nikon/nikon-nis-20x-rgb-eucalyptus-zenodo8006449.tif | 9045322 | CC-BY-4.0 | 2.4285714285714288e-07 m | same method (0.24285714285714288 µm) |
| derived/nikon-nis-40x-h3k9me3-crop.tif | 551116 | CC-BY-4.0, derived | 1.625e-07 m | same |
| derived/nikon-nis-20x-rgb-eucalyptus-crop.tif | 621322 | CC-BY-4.0, derived | 2.4285714285714288e-07 m | same |
| leica-tcs/leica_stack_Series014_z000_ch00.tif (+z001, z002, .lei, .txt) | 109968 each | CC0 (samples.scif.io) | 2.929688e-06 m | vendor text "Voxel-Width [µm] = 2.929688"; sidecar leica_stack.txt gives 7.5e-4 m / 256 = 2.9296875e-06 m |
| hamamatsu/test3-TRITC 2 (560).ndpi | 3064887 | CC-BY-4.0 (Manuel Stritt, OME downloads) | 2.281750559028887e-07 m | 0.01 m / XResolution 43826 px/cm, the formula of OpenSlide and Bio-Formats NDPIReader |
| hamamatsu/hamamatsu-orca-rgb-nocal-zenodo7845067.tif | 3137106 | "other-pd" | none (negative test) | only 90 dpi print resolution, no vendor tag |
| zeiss/zeiss-axiovision-rgb-nocal-rsciio.tif | 704 | GPL-3.0 (RosettaSciIO) | none (negative test) | RosettaSciIO test expects no units without force_read_resolution |
| zeiss/zeiss-sem-leo-2160grating-512.tif | 298932 | CC-BY-4.0 (David Mankus, OME downloads) | 2.233e-08 m | tifffile CZ_SEM ap_image_pixel_size 22.33 nm; repo reader already gives this |
| zeiss/zeiss-sem-sigma-AWM2-04_01-latin1-um.tif | 3252534 | CC-BY-4.0 (Johannes Preußner, zenodo 16760282) | 1.595e-06 m | Bio-Formats PR 4353 text and tifffile ap_image_pixel_size; repo reader already gives this |
| zeiss/zeiss-sem-sigma-AWM2-04_06.tif | 3252588 | same | 2.762378e-08 m | tifffile ap_image_pixel_size 27.62 nm; repo reader already gives this |

Not copied (licence unverified), kept in `dl/`:

| file (in dl/) | size | why not copied | expected pixel size | source |
|---|---|---|---|---|
| leica/lyso-C00.tif | 114458 | Leica XLEF/TIF set: no licence file on OME downloads; Leica said only "you may use for testing" (Bio-Formats PR 3747) | 8.551636712754061e-08 m | TIFF tags; xlif sidecar Length 4.215985e-05 m / (494 - 1) = 8.5516937e-08 m |
| leica/nav-pmd1-C00.tif | 16672 | same | 6.416486577693486e-07 m | TIFF tags; xlif Length 8.148938e-05 m / (128 - 1) = 6.416487e-07 m |
| aics/4c_3Z_pyramid.tiff + .tiff_metadata.xml | 2193316 | AICSImageIO S3 test resource, no licence stated | 1.0833333333333332e-07 m (sidecar only) | sidecar `<Scaling><Items><Distance Id="X"><Value>` |
| scifio/fv/10-31 E1.tif | 177040484 | licence fine (CC0) but too large; derived page 0 is in vendor-samples | 1.2429611524567008e-06 m | tifffile |

---

## 1. Olympus / Evident

### 1a. cellSens, analySIS, iTEM, Radius: OlympusSIS tag 33560 (and 33471)

**Files**

- `olympus-sis-quemesa-rsciio.tif`: <https://github.com/hyperspy/rosettasciio/raw/main/rsciio/tests/data/tiff/olympus_SIS.tif>, 101042 bytes, GPL-3.0 (same terms as the existing test files). Make "Olympus Soft Imaging Solutions", Model "Quemesa" (TEM camera). Two pages: page 0 is a JPEG RGB preview without the SIS tag, page 1 is uint16 with the SIS tag. Expected 2.392791775876109e-11 m (tifffile); RosettaSciIO `test_olympus_SIS` asserts `assert_allclose(axis.scale, 2.3928e-11)` in metres for both axes of the second image. Magnification field: 600000.
- `olympus-cellsens-sc50-4x-zenodo7845067.tif`: <https://zenodo.org/records/7845067> file "Patient-derived cells_24h after isolation.tif", 4948990 bytes. Zenodo licence field "other-pd" (Other, public domain); creators Anna Piotrowska, Oliwia Król. Make "Olympus", Model "SC50" (cellSens camera), uncompressed 8-bit 2560x1920, single page. Expected 5.506001494814109e-07 m (tifffile read_sis), magnification 4.0. Its sibling "Patient-derived cells_before first passage.tif" (4948990 bytes) has the same structure (seen remotely, not downloaded).
- `derived/olympus-cellsens-sc50-4x-crop.tif` (361470 bytes): same file with only the first 2 of 30 strips (128 rows). All metadata bytes (IFD values, EXIF IFD, SIS block) are verbatim; only offsets past the cut, ImageLength and the strip counts were changed (`scripts/crop_strips.py`). tifffile and the Pillow prototype read 5.506001494814109e-07 m from it. Public domain, so the modification needs no notice, but say "cropped" in the test README.
- tifffile's own SIS test files (`sis/4A5IE8EM_F00000409.tif`, expected 0.108 µm, and `sis/110.tif`, expected 0.2713757378 µm, magnification 20) are not publicly downloadable. Expected values quoted from `tests/test_tifffile.py` only.

**Where the calibration lives**

Tag 33560 (OlympusSIS), type LONG, count 1: the value is an absolute file offset to a little-endian structure (always little-endian in the code of both tifffile and Bio-Formats). In Pillow: `im.tag_v2[33560]` is an int (checked).

From tifffile `read_sis` (verbatim struct formats):

```
header, 60 bytes at the offset:  '<4s6xhhhhh6x32sH'
  magic(4s) == b'SIS0', 6 pad, minute, hour, day, month, year (int16 each;
  year is +1900, month is 0-based), 6 pad, name(32s), tagcount(uint16 at +58)
then tagcount entries of 8 bytes: '<hhI'  (tagtype int16, count int16, offset uint32 absolute)
for tagtype == 1 ("general data"), 112 bytes at offset:  '<10xhdd8xd2x34s32s'
  +10 lenexp  int16
  +12 xcal    float64
  +20 ycal    float64
  +28 8 bytes skipped
  +36 mag     float64
  +44 2 pad
  +46 camname 34s
  +80 pictype 32s
pixel size in metres:  xcal * 10**lenexp,  ycal * 10**lenexp
```

Both samples have lenexp = -6, so xcal is in micrometres there. tifffile skips tagtype 10 (channel data). Bio-Formats `SISReader` reads the same block but only uses the first entry; it also swaps in the next double when xcal and ycal differ (`if |x - y| > eps: x = y; y = readDouble()`), which looks like a guard for a variant layout (**unverified**, no such file found). Bio-Formats only accepts the exponent if -12 <= lenexp <= 12.

**Pillow recipe** (verified on both files and the derived crop):

```python
for page in range(getattr(im, "n_frames", 1)):  # rsciio file: tag on page 1
    im.seek(page)
    off = im.tag_v2.get(33560)
    if off is None:
        continue
    fp = im.fp
    fp.seek(off)
    head = fp.read(60)
    if head[:4] != b"SIS0":
        continue  # tifffile test 'cirb_NOT_SIS.tif' has a bogus 33560
    n = struct.unpack_from("<H", head, 58)[0]
    fp.seek(off + 60)
    ent = fp.read(8 * n)
    for i in range(n):
        ttype, _, toff = struct.unpack_from("<hhI", ent, 8 * i)
        if ttype == 1:
            fp.seek(toff)
            b = fp.read(112)
            lenexp, xcal, ycal = struct.unpack_from("<hdd", b, 10)
            return xcal * 10.0**lenexp, ycal * 10.0**lenexp
```

Note: `im.fp` is the open file (or BytesIO when bytes were passed), so this works for all inputs `calibration.read()` accepts. RosettaSciIO assigns `pixelsizex` to y and `pixelsizey` to x; with square pixels that does not matter.

**Tag 33471 (OlympusINI)**: ASCII INI text (sections `[Dimension]`, `[Band]`, `[Z]`, `[Time]`, `[ASD]`). tifffile's `olympus_ini_metadata` parses it but reads no spatial calibration from it; in both tifffile and Bio-Formats the pixel size comes from 33560 only. Whether the INI ever carries a pixel size: **unverified** (no sample with 33471 found; both samples above have only 33560).

**Tag 34853 variant** (Bio-Formats `SIS_TAG_2`, which collides with GPSInfo; Bio-Formats requires Make starting with "Olympus"): Bio-Formats seeks to the tag value, scans byte by byte for the two characters "IS", skips 28 bytes, reads a long `p`, seeks to `p - 84`, reads two doubles and multiplies by 1000 to get µm. Long size, endianness and the unit before the x1000 are **unverified**; no sample found. tifffile does not decode this variant.

### 1b. FluoView: MM_Header tag 34361 (and MM_Stamp 34362)

**File**

- Original: <https://samples.scif.io/10-31_E1.zip> (50556723 bytes zip, contains "10-31 E1.tif", 177040484 bytes, 336 pages, 512x512 uint16, FluoView 4.1.14 on an FV500). Licence CC0 per the samples.scif.io table; readme credits Timothy Gomez, UW-Madison.
- `derived/fluoview-fv500-10-31_E1-page0.tif` (542450 bytes): the original's first 542450 bytes (header, IFD0, all its tag data and its strips) with IFD0's next-IFD pointer set to 0 (`scripts/first_page.py`). No other byte changed. Expected 1.2429611524567008e-06 m for X and Y (tifffile `fluoview_metadata` Dimensions X and Y, Resolution 1.2429611524567008, unit "µm"; tifffile series coord_scales agree).
- tifffile's tests use `fluoview/lsp1-V-laser0.3-1.tif` (expects X and Y step 0.041 µm) and `fluoview/120816_bf_f0000.tif`; neither is public.

**Where the calibration lives**

Tag 34361, type BYTE (1), count 1454 in this file. Pillow returns `bytes` for it (checked). Packed struct, byte order of the TIFF file. tifffile `TIFF.MM_HEADER` (numpy record, no alignment), with offsets computed from it and matching Bio-Formats' `skipBytes(284)`:

```
  0 HeaderFlag   i2
  2 ImageType    u1
  3 ImageName    S257
260 OffsetData   u4
264 PaletteSize  i4
268 OffsetPalette0 u4
272 OffsetPalette1 u4
276 CommentSize  i4
280 OffsetComment u4
284 Dimensions   10 x MM_DIMENSION (100 bytes each)
      +0  Name       S16   ('X', 'Y', 'Z', 'T', 'CH', 'WAVELENGTH', 'TIME', 'XY', 'EVENT', 'EXPOSURE')
      +16 Size       i4
      +20 Origin     f8
      +28 Resolution f8    (step per pixel, in Unit)
      +36 Unit       S64   (here b'\xb5m', i.e. Latin-1 "µm")
1284 OffsetPosition u4, then MapType i2, MapMin f8, MapMax f8, MinValue f8,
     MaxValue f8, OffsetMap u4, Gamma f8, Offset f8, GrayChannel MM_DIMENSION,
     OffsetThumbnail u4, VoiceField i4, OffsetVoiceField u4
```

Pixel size = Resolution of the dimension named "X" (and "Y") times the unit. tifffile maps units with its SU2UM table (nm, µm, um, micron(s), micrometer(s), mm, cm, m, and long forms); Bio-Formats ignores the unit string and assumes µm. Unit bytes are Latin-1 (0xB5), so decode with latin-1, not UTF-8.

**Pillow recipe** (verified):

```python
raw = im.tag_v2.get(34361)  # bytes
bo = "<" if im.tag_v2.prefix == b"II" else ">"
for i in range(10):
    base = 284 + 100 * i
    name = raw[base : base + 16].split(b"\0")[0].decode("latin-1").strip().upper()
    size, origin, res = struct.unpack_from(bo + "idd", raw, base + 16)
    unit = raw[base + 36 : base + 100].split(b"\0")[0].decode("latin-1").strip()
```

Detection: Bio-Formats accepts (description contains "FLUOVIEW" and tag 34361 present) or tag 34362 present. The description here contains "FLUOVIEW Version=Version 4.1.14". tifffile's `is_fluoview` is "34362 in tags".

Second copy of the value: tag 285 (PageName) holds tab-separated text `[Primary Dimensions]\nName\tX\tY\r\nOffset\t0.000000\t0.000000\r\nResolution\t1.242961\t1.242961\r\nUnits\tµm\tµm ...`. Bio-Formats `parsePageName` reads the "Resolution" line (used for its Andor path).

**Andor iQ**: Bio-Formats' FluoviewReader comment says Andor TIFF was merged into it because the formats are "very similar"; Andor iQ files with tag 34361 decode the same way. **Unverified**: no Andor iQ sample found. Andor Solis tags 4864 to 5030 (tifffile `andor_tags`) hold temperature, exposure, frames, chip size and so on, but no spatial calibration in tifffile's list.

### 1c. Newer OIR / FV31S / cellSens VSI exports

**Gap.** The only OIR "TIFF exports" found on OME downloads (`Olympus-OIR/etienne/*.ome.tif`, CC-BY-4.0) were written by "OME Bio-Formats 5.2.0-DEV", not by Olympus software; their OME-XML gives PhysicalSizeX 1.242961138804478 µm and is already handled by the OME reader. The `Clipboard-*.tif` files there are ImageJ RGB screenshots with no calibration. No FV31S-written TIFF sample found. cellSens `.vsi` files (OME `CellSens/` folders) are not TIFF exports and were not examined.

---

## 2. Nikon NIS-Elements TIFF

**Files**

- `nikon-nis-40x-h3k9me3-zenodo7677827.tif`: <https://zenodo.org/records/7677827> file `single_plane_1-2000_2xy01c1.tif`, 8415436 bytes, CC-BY-4.0, creator Sarah Mangiameli. 2048x2048 uint16, objective "Apo LWD 40x WI λS DIC N2". Sibling records 7677835 and 7677868 have the same structure (seen remotely).
- `nikon-nis-20x-rgb-eucalyptus-zenodo8006449.tif`: <https://zenodo.org/records/8006449> file `C1_E2_M_ROI.tif`, 9045322 bytes, CC-BY-4.0, creator Rafael Keret. 2000x1500 RGB, objective "Plan Apo λ 20x", dZoom 0.7. Record 8006637 has the same structure.
- Derived: `nikon-nis-40x-h3k9me3-crop.tif` (551116 bytes, 128 rows) and `nikon-nis-20x-rgb-eucalyptus-crop.tif` (621322 bytes, 96 rows), made with `crop_strips.py`; all Nikon tag bytes verbatim. CC-BY needs attribution and a note that the files were cropped.

Expected: 0.1625 µm and 0.24285714285714288 µm. Independent source: the nd2 package's CLx Lite decoder (`nd2._parse._clx_lite.json_from_clx_lite_variant`) applied to the `SLxPictureMetadata` record inside tag 65331 gives `dCalibration` 0.1625 and 0.24285714285714288 with `bCalibrated` True and `dAspect` 1.0. Plausibility: 6.5 µm camera pixels / 40 = 0.1625. tifffile has no Nikon parser; Bio-Formats' value for these files is **unverified** (see below).

**Where the calibration lives (observed in these two files; no public spec)**

Neither file has Make, Model, Software or ImageDescription. All metadata is in private tags 65325 to 65333:

| tag | type | content observed |
|---|---|---|
| 65325 | DOUBLE | 7293.57 / 894.11 (equals the 4th value of 65329; looks like a time in ms, **unverified**) |
| 65326 | DOUBLE | **0.1625 / 0.242857...: equals dCalibration (µm per pixel)** |
| 65327 | DOUBLE | 1.0 (possibly dAspect, **unverified**) |
| 65328 | DOUBLE | 1.0 (only in the first file) |
| 65329 | DOUBLE x4 | stage X, Y, Z and the 65325 value (**unverified** meaning) |
| 65330 | BYTE | binary CLx Lite blocks (camera, ROI, text info) |
| 65331 | BYTE | container "MetadataTiffV1_0" holding `SLxPictureMetadata` (CLx Lite) |
| 65332 | BYTE | container with "AppInfo_V1_0" / "CustomDataV2_0" (UTF-16, includes an XML comment) |
| 65333 | BYTE x4 | zeros |

Tag 65331 layout as observed: uint32 1 (entry count), uint32 16 (name length in UTF-16 units), UTF-16LE "MetadataTiffV1_0", uint32 1, uint32 0, uint32 data length (0x0EA0 = 3744), uint32 data offset (0x38 = 56); 56 + 3744 = 3800 = tag count. The data at 56 starts with the CLx Lite record `0x0B 0x13 "SLxPictureMetadata\0"` (type 11 = LEVEL, name length 19 including the null).

CLx Lite records (from nd2's `_clx_lite.py`): `uint8 type, uint8 name_len` (in UTF-16 units, including the terminating null), then `name_len * 2` bytes of UTF-16LE name, then the value. Types: 1 bool (1 byte), 2 int32, 3 uint32, 4 int64, 5 uint64, 6 double (8 bytes LE), 7 void pointer (8 bytes), 8 UTF-16 string ending with 0x0000, 9 byte array, 11 LEVEL (uint32 item count, uint64 length, nested), 76 ('L') zlib-compressed (skip 10 bytes, inflate).

Units: µm. Bio-Formats' ND2Handler treats `dCalibration` as the pixel size in µm (`pixelSizeX = pixelSizeY = dCalibration`), same for ND2.

**Pillow recipe** (verified on both files and both crops; Pillow returns float for 65326 and bytes for 65331):

```python
key = b"\x06\x0d" + "dCalibration\0".encode(
    "utf-16-le"
)  # type 6 double, name length 13
meta = im.tag_v2.get(65331)
i = meta.find(key)
um = struct.unpack_from("<d", meta, i + len(key))[0]  # value follows the name
key = b"\x01\x0c" + "bCalibrated\0".encode("utf-16-le")  # type 1 bool, name length 12
j = meta.find(key)
calibrated = meta[j + len(key)] != 0
# simpler, same value in both files: um = im.tag_v2[65326]
```

Recommendation: prefer the named `dCalibration` in 65331 (self-describing), fall back to 65326, and treat `bCalibrated == 0` as uncalibrated. Detection: tag 65331 starts with `b"\x01\x00\x00\x00\x10\x00\x00\x00" + "MetadataTiffV1_0".encode("utf-16-le")`.

**Bio-Formats mismatch**: `NikonElementsTiffReader` claims files with tag 65332 and parses its text as XML (`<NIKON>` + text from the first "<"). In these files 65332 is a binary UTF-16 container, so what Bio-Formats returns for them is **unverified** (Java not run). Older NIS versions writing XML text into 65332 (with `<dCalibration runtype="double" value="..."/>`) are what that reader expects; no such sample found. The user's guess "tag 65330" holds other blocks here, not the calibration.

**Nikon EZ-C1** (`NikonTiffReader`, Software contains "EZ-C1"): ImageDescription lines split on tabs, keys "document label" and "document scale" give per-dimension labels and scales. No sample found; **unverified**.

---

## 3. Leica

### 3a. LAS X TIFF export ("XLEF/TIF")

**Files** (licence **unverified**, so not in vendor-samples):

- `dl/leica/lyso-C00.tif` = <https://downloads.openmicroscopy.org/images/Leica-XLEF/Lysosomes%20actin%20in%20motion/XLEF-TIF%20Lysosomes_actin_in_motion/1_Series001_Crop001_Crop001--t0000--Z00--C00.tif>, 114458 bytes.
- `dl/leica/nav-pmd1-C00.tif` = `.../Leica-XLEF/MaF%20in%20Navigator%2012bit%203s%20z5/XLEF-TIF%20MaF%20in%20Navigator%2012bit%203s%20z5/Position%201/Position%201_pmd_1/Position%201_pmd_1--Z00--C00.tif`, 16672 bytes.
- Sidecars: `dl/leica/lyso.xlef`, `dl/leica/lyso1.xlif`, `dl/leica/nav.xlif`.
- Licence: the OME `Leica-XLEF/` tree has no COPYING or readme. The set is Leica's "official test dataset" posted in Bio-Formats PR 3747 (links to webshare3.leica-microsystems.com/fiji/...) with only "that you may use for testing". Not clearly redistributable; ask Leica or skip committing.

**Where the calibration lives**: in the plain resolution tags, with ResolutionUnit = 3 (centimetre). ImageDescription is exactly `<LMSIOManager><ProductVersion>2,0,0,0</ProductVersion><BitShift>UnProcessed</BitShift></LMSIOManager>`. XResolution is a RATIONAL with the numerator pinned at 2^32 - 1: lyso (4294967295, 36729), nav (4294967295, 275586).

pixel size (m) = 0.01 / XResolution. Lyso 8.551636712754061e-08 m; nav 6.416486577693486e-07 m.

Independent check from the xlif sidecar `<DimensionDescription DimID="1" NumberOfElements=N Length=L Unit="m">`: L / (N - 1) gives 8.5516937e-08 m (lyso, L 4.215985e-05, N 494) and 6.416487e-07 m (nav, L 8.148938e-05, N 128). The TIFF value matches L/(N-1) to 7e-6 relative (lyso) and 6e-9 (nav); L/N does not match (8.534e-08, 6.366e-07).

**Pillow recipe** (verified): `desc.startswith("<LMSIOManager")` and `tags[296] == 3`, then `0.01 / float(tags[282])`, `0.01 / float(tags[283])`. Keep the vendor check, since the plain resolution tags are print resolution in most other files.

### 3b. Leica TCS NT / LCS (older, 2005)

**Files**: `leica-tcs/` from <https://samples.scif.io/leica_stack.zip> (83581 bytes zip): three 109968-byte TIFFs, `leica_stack.lei`, `leica_stack.txt`, `readme.txt`. CC0 per samples.scif.io; readme credits Clay Glennon, Wisconsin National Primate Research Center. Software tag "TCSNTV", private tag 33923 (LeicaMagic). No X/YResolution tags.

**Where the calibration lives**: ImageDescription is an INI-like text starting with `[Parameter-Settings]`, lines `key<TAB>=<TAB>value` with CRLF; unit-bearing keys put the unit in brackets after a tab: `Voxel-Width\t[µm]\t=\t2.929688`, `Voxel-Height\t[µm]\t=\t2.929688` (also `Size-Width [µm] = 750.000000`, `Format-Width = 256`). The µ is the single Latin-1 byte 0xB5.

Expected 2.929688e-06 m. Independent: `leica_stack.txt` (vendor sidecar) says Dimension_0 Logical Size 256, Physical Length 7.500000e-004 m, giving 2.9296875e-06 m (here L/N, unlike LAS X).

Bio-Formats `TCSReader` looks for keys `VoxelSizeX/Y/Z` in a description starting with "[", not `Voxel-Width`; with the .lei present Bio-Formats routes the set to `LeicaReader` instead. Bio-Formats' value for this file is **unverified**.

**Pillow recipe** (verified): regex `^(Voxel-Width|Voxel-Height)\s*\[(.+?)\]\s*=\s*([0-9.eE+-]+)` per line, unit from the bracket via the existing `metres_per_unit()` (Pillow gives the text as Latin-1 str, so "µm" maps directly).

### 3c. LAS AF TIFF exports with XML sidecar

**Gap / unverified.** No LAS AF (pre-LAS X) TIFF export sample found. Leica SCN (whole-slide, OME `Leica-SCN/openslide`) was not examined.

---

## 4. Zeiss light microscopy (AxioVision, ZEN)

- **AxioVision TIFF** (`zeiss-axiovision-rgb-nocal-rsciio.tif`, 704 bytes, GPL-3.0; the BW twin is already in the repo): only Model "AxioCamERc5s", 150 dpi print resolution, no vendor tag. RosettaSciIO's 169.333 µm with `force_read_resolution` is just 25400/150. Bio-Formats `ZeissTIFFReader` header comment: the TIFF planes carry no metadata; the calibration is in a companion `<name>_meta.xml` (blocks `<Tags>` with V/I/A triples, `<Scaling>`). The repo's current expectation (None) is right.
- **ZEN TIFF export**: `dl/aics/4c_3Z_pyramid.tiff` (2193316 bytes, from the AICSImageIO public S3 test bucket, licence **unverified**) has only 300 dpi print resolution. Its sidecar `4c_3Z_pyramid.tiff_metadata.xml` (root `<ImageMetadata>`) holds `<Scaling><Items><Distance Id="X"><Value>1.0833333333333332E-07</Value><DefaultUnitFormat>µm</DefaultUnitFormat>` (value in metres). Whether ZEN itself names the sidecar `<file>.tiff_metadata.xml` or AICS renamed it is **unverified**.
- **Tag 34118 / 65000**: in all Zeiss light-microscopy TIFFs seen, neither tag is present. 34118 is the SEM tag (already supported). tifffile uses 65000 only for Argos AVS, EER, EPICS and Nuvu, nothing Zeiss.
- Conclusion: Zeiss LM TIFFs need a sidecar reader (the extension knows the linked image path, so `<stem>_meta.xml` or `<file>_metadata.xml` next to it could be read), or nothing.

Bonus, existing Zeiss SEM reader: three more CC-BY-4.0 LEO/Sigma files from OME downloads (`zeiss/zeiss-sem-*`). The repo's reader already gives 2.233e-08 m, 1.595e-06 m and 2.762378e-08 m, matching tifffile's `ap_image_pixel_size` (22.33 nm, 1.595 µm, 27.62 nm). The `04_01` file is the Bio-Formats issue 4352 case: its text uses Latin-1 "µm" and Bio-Formats showed 3.19 µm before PR 4353, 1.595 µm after. The repo reader is immune because it uses the unnamed numeric field. `zeiss-sem-leo-2160grating-512.tif` (298932 bytes) is small enough to commit; it is 512 wide, so it exercises the `1024 / width` scaling (Pixel Size 11.16 nm at 1024, image pixel 22.33 nm).

---

## 5. Hamamatsu

- **NDPI** (`hamamatsu/test3-TRITC 2 (560).ndpi`, 3064887 bytes, from <https://downloads.openmicroscopy.org/images/Hamamatsu-NDPI/manuel/>, CC-BY-4.0, (c) Manuel Stritt; also on samples.scif.io as the DAPI channel). Make "Hamamatsu", Model "C9600-12", Software "NDP.scan 2.5.89", private tags 65420 to 65457 (65420 = file format marker, 65421 = source lens 40.0). XResolution (43826, 1), ResolutionUnit 3 (cm). Pixel size = 0.01 m / 43826 = 2.281750559028887e-07 m. Source of the formula: OpenSlide `ndpi_set_props` calls `_openslide_tifflike_set_resolution_props`, which uses 10000 / XResolution µm for RESUNIT_CENTIMETER; Bio-Formats `NDPIReader` uses `ifd.getXResolution()` the same way. Pillow opens it and reads the tags (checked). Recipe: Make == "Hamamatsu" and 65420 in tags and ResolutionUnit == 3, then `0.01 / XResolution`. Note: whole-slide pyramids; the first IFD is the full-resolution level. Files over 4 GB use 64-bit offsets that Pillow cannot parse.
- **HCImage / ORCA camera TIFFs**: the only one found (`hamamatsu-orca-rgb-nocal-zenodo7845067.tif`, public domain) is an RGB export with 90 dpi and no vendor tag: no calibration (negative test).
- **Streak camera (HPD-TA)**: RosettaSciIO `tiff_hamamatsu.zip` (GPL-3.0, 387170 bytes) holds wavelength/time axes, not spatial pixel size; not relevant for a scale bar. Not copied.

## 6. Oxford Instruments / Andor

- Andor iQ: same MM_Header as FluoView (see 1b), **unverified** for lack of a sample.
- Andor Solis TIFF tags 4864 to 5030: no spatial calibration among tifffile's named tags. tifffile's test file `andor/light sheet 512px.tif` is not public.
- Oxford Instruments (AZtec etc.): Bio-Formats `OxfordInstrumentsReader` is a non-TIFF format. No Oxford TIFF sample found. **Gap.**

---

## Gaps and suggestions

- No sample for: FluoView FV10-ASW / FV31S native TIFF beyond the FV500 one, OIR exports written by Olympus software, Olympus 34853 variant, older Nikon XML-in-65332 TIFFs, Nikon EZ-C1, Leica LAS AF TIFF, Andor iQ, Oxford.
- Committable now (small, licence known): `olympus-sis-quemesa-rsciio.tif` (GPL-3, 101 KB), `derived/olympus-cellsens-sc50-4x-crop.tif` (PD, 361 KB), `derived/fluoview-fv500-10-31_E1-page0.tif` (CC0, 542 KB), `derived/nikon-nis-*-crop.tif` (CC-BY-4.0, 551 and 621 KB), `leica-tcs/leica_stack_Series014_z000_ch00.tif` (CC0, 110 KB), `zeiss/zeiss-sem-leo-2160grating-512.tif` (CC-BY-4.0, 299 KB). The CC-BY files need attribution lines in tests/data/README.md. `.gz` does not help much (Nikon 16-bit 8.4 MB to 3.0 MB), so the strip crops are the better route.
- Leica LAS X: recipe is solid, sample licence is not. Ask Leica, or write a synthetic test (description `<LMSIOManager>...`, unit cm, XResolution (4294967295, 36729)).
