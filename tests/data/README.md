# Test images

These instrument files come from the test data of
[RosettaSciIO](https://github.com/hyperspy/rosettasciio)
(`rsciio/tests/data/tiff/`), GPL-3.0, by the HyperSpy developers. The
expected pixel sizes in `tests/test_calibration.py` are the ones
RosettaSciIO's own tests (`rsciio/tests/test_tiff.py`) check.

| here | there |
|---|---|
| `imagej.tif` | `test_loading_image_saved_with_imageJ.tif` |
| `imagej-no-scale.tif` | `test_loading_image_saved_with_imageJ_no_scale.tif` |
| `digitalmicrograph.tif` | `test_loading_image_saved_with_DM.tif` |
| `fei-helios.zip` | `tiff_FEI_Helios.zip` |
| `zeiss-sem.zip` | two of the files in `tiff_Zeiss_SEM.zip` |
| `jeol-sightx-tem-mag.tif.gz` | `JEOL-SightX-TEM-mag-dummy.tif.gz` |
| `zeiss-axiovision.tif` | `optical_Zeiss_AxioVision_BW.tif` |

## Other makers

| here | source | licence |
|---|---|---|
| `olympus-sis-quemesa.tif` | RosettaSciIO test data, `olympus_SIS.tif` | GPL-3.0 |
| `zeiss-axiovision-rgb.tif` | RosettaSciIO test data, `optical_Zeiss_AxioVision_RGB.tif` | GPL-3.0 |
| `olympus-cellsens-sc50-crop.tif` | "Patient-derived cells_24h after isolation.tif" by Anna Piotrowska and Oliwia Król, [Zenodo 7845067](https://zenodo.org/records/7845067); cropped to the first 128 rows | public domain (Zenodo: other-pd) |
| `fluoview-fv500-page0.tif` | first page of "10-31 E1.tif" from [samples.scif.io](https://samples.scif.io/) (`10-31_E1.zip`), by Timothy Gomez, UW-Madison | CC0 |
| `leica-tcs.tif` | `leica_stack_Series014_z000_ch00.tif` from [samples.scif.io](https://samples.scif.io/) (`leica_stack.zip`), Wisconsin National Primate Research Center, UW-Madison | CC0 |
| `nikon-nis-40x-crop.tif` | `single_plane_1-2000_2xy01c1.tif` by Sarah Mangiameli, [Zenodo 7677827](https://zenodo.org/records/7677827) ("Images of H3K9me3 Immunostain in IMR90 Cells"); cropped to the first 128 rows | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| `nikon-nis-20x-rgb-crop.tif` | `C1_E2_M_ROI.tif` by Rafael Keret, [Zenodo 8006449](https://zenodo.org/records/8006449) ("Eucalyptus grandis xylem microsections for algorithm training"); cropped to the first 96 rows | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |

The crops keep every metadata byte; only the pixel rows after the first
strips are cut (and the offsets, image height and strip counts that
change with them). Expected values: tifffile 2026.11.16 for Olympus and
FluoView, the nd2 package's decoder for Nikon, the file's own sidecar
text for Leica TCS.

Leica LAS X, Hamamatsu NDPI and Zeiss ZEN metadata files are tested with
generated files only: the real samples checked by hand (Leica's own test
set, an OME CC-BY NDPI file of 3 MB, an AICSImageIO ZEN export) either
have no clear licence or are too large to keep here.
