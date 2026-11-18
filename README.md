# Scale Bar for Inkscape

Put a calibrated scale bar on microscope images in Inkscape:
**Extensions > Images > Scale Bar...** Select one or more images (or
nothing, for every image in the drawing). The bar sits in a corner of
each image, with its length written above it, and follows the image
when you move, scale or rotate them together.

The pixel size is read from the image file:

| Files | Where the pixel size is |
|---|---|
| OME-TIFF | OME-XML `PhysicalSizeX/Y` and units |
| ImageJ / Fiji TIFF | `unit=` in the description, X/Y resolution |
| Thermo Fisher / FEI SEM and FIB TIFF | `[Scan] PixelWidth`, or `[IRBeam] HFW` / `[Image] ResolutionX` |
| Zeiss SEM TIFF | tag 34118, pixel size at 1024 wide |
| Gatan DigitalMicrograph TIFF | tags 65009/65010, unit in 65003 |
| JEOL SightX TEM TIFF (MAG mode) | camera resolution / magnification |
| Olympus/Evident cellSens, analySIS TIFF | SIS block (tag 33560), on any page |
| Olympus FluoView TIFF (also Andor iQ, untested) | MM header (tag 34361), X and Y records |
| Nikon NIS-Elements TIFF | `dCalibration` in tag 65331, if calibrated |
| Leica LAS X TIFF export | resolution tags in cm (only with Leica's description) |
| Leica TCS TIFF | `Voxel-Width/Height` in the description |
| Hamamatsu NDPI | resolution tags in cm (only for Hamamatsu files) |
| Zeiss ZEN export | `<image>_metadata.xml` next to the image |

The vendor rules follow [RosettaSciIO](https://github.com/hyperspy/rosettasciio)'s
TIFF reader, and the tests check them against its real instrument files
with the values its own tests expect. The plain TIFF resolution tags
are deliberately not used: exported images usually carry a print
resolution there (72 or 300 dpi), not a calibration.

For PNG or JPEG exports, or anything else without readable metadata:

- **type the pixel size** (Calibration tab), such as `0.325 µm`, or
- **draw a line** along something of known length in the image (a scale
  bar burnt in by the microscope, a grid), select it with the image, and
  give its length.

Either is stored on the image (`data-pixel-size-m`), so running the
extension again later, after resizing the image, say, needs no input
and replaces the old bar.

Options: length (auto: a round 1, 2 or 5 about a fifth of the image
width; or e.g. `20 µm`), corner, colour (automatic picks white or black
from the image under the bar), background box, label, font, sizes.

Works in the Inkscape Flatpak: it needs only Python, numpy and Pillow,
and reads linked files as well as images embedded in the drawing.

## Install

    dev/install.sh            # symlinks into your Inkscape extensions folder
    dev/install.sh --uninstall

Or copy `scalebar.inx`, `scalebar.py` and `calibration.py` into your
Inkscape extensions folder. Restart Inkscape.

## Limits

- Inkscape itself cannot display 32-bit float TIFFs (it shows a broken
  image icon); convert those to 8 or 16 bit first. The scale bar is
  still calibrated correctly.
- The bar is placed in the corner of the whole image, not of a clipped
  part of it.
- Not yet read: Zeiss AxioVision's `_meta.xml` files, Leica LAS AF,
  Oxford Instruments, TVIPS (no samples found to check them against);
  JEOL STEM and diffraction images. Nikon files from older NIS-Elements
  versions that keep their metadata as XML may not be recognised.
- From Inkscape's command line, extensions get no selection, so every
  image is processed:
  `inkscape fig.svg --actions="org.sandbranch.filter.scalebar.noprefs;export-filename:out.svg;export-do"`

## Tests

    python3 -m pytest tests/

`tests/test_calibration.py` checks the calibration reader on the
instrument files in `tests/data` (see its README) and on generated
OME-TIFF and ImageJ files; `tests/test_scalebar.py` runs the extension
through inkex and checks bar lengths, placement with
`preserveAspectRatio`, transforms, line and typed calibrations, the
automatic colour and replacing an old bar. They need inkex 1.4
(`pip install --no-deps inkex==1.4.0` plus lxml, numpy, pillow,
tinycss2, cssselect, pyparsing, packaging), as in the GitHub workflow.

Also checked by hand: run through Inkscape 1.4.4 (Flatpak) on a Thermo
Fisher Helios SEM image, whose own burnt-in 500 µm bar is 151 pixels
long, end caps included; the file's calibration gives 148.3.

## Licence

GPL-3.0-or-later, see `COPYING`. Test images: see `tests/data/README.md`.
