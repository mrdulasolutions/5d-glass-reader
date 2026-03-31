# 5D Glass Eternal Drive — COTS SSLE Edition
**mrdulasolutions/5d-glass-reader** · indie hacker build · March 2026

World's first fully commercial-off-the-shelf subsurface laser engraving (SSLE) glass memory drive + reader.
No femtosecond lasers. No lab. No gatekeepers. Just a UV laser, a Raspberry Pi, and some fused silica.

**Writer**: xTool F2 Ultra UV 5W — engraves dots *inside* glass
**Reader**: Raspberry Pi 5 + HQ Camera + motorized XY stage
**Media**: K9 optical crystal (calibration) · JGS2 fused silica (production)
**Status**: v0.2 — full encode → engrave → scan → decode pipeline with Reed-Solomon ECC + motorized stage

---

## Table of Contents
1. [How It Works](#how-it-works)
2. [Hardware & Cost](#hardware--cost)
3. [xTool F2 Ultra — Specs & Settings](#xtool-f2-ultra--specs--settings)
4. [Storage Density](#storage-density)
5. [Software Setup](#software-setup)
6. [End-to-End Workflow](#end-to-end-workflow)
7. [3D Volumetric Mode](#3d-volumetric-mode-v03)
8. [File Structure](#file-structure)
9. [Roadmap](#roadmap)

---

## How It Works

```
Any file  →  encode_ssle.py  →  dot-grid PNG  →  xTool F2 Ultra  →  glass disc
                                                  (subsurface dots)
glass disc  →  Pi camera  →  decode_ssle.py  →  original file recovered
```

1. `encode_ssle.py` converts your file to a binary dot-grid PNG (dot = 1, blank = 0) with Reed-Solomon error correction baked in and 4-corner fiducial markers for perspective correction on decode.
2. Load the PNG into **xTool Studio** → Inner Engraving → Dotting mode. The machine fires the UV laser *inside* the glass at each dot position, creating a permanent white scattering point.
3. Place the disc under the Pi camera. `decode_ssle.py` finds the fiducials, corrects perspective, samples the grid, RS-decodes, and writes the original file back out.

**3D mode** (`encode_ssle_3d.py`) outputs an STL instead — xTool Studio engraves dots at multiple Z depths, multiplying capacity by the number of layers.

---

## Hardware & Cost

| Component | Price (Mar 2026) | Buy Direct |
|-----------|-----------------|------------|
| **xTool F2 Ultra UV 5W** (writer) | **$4,249** | [xtool.com → F2 Ultra UV](https://www.xtool.com/products/xtool-f2-ultra-uv-5w-uv-laser-engraver) |
| **K9 Rectangle Crystal** (calibration blank, 100×50×50mm) | **~$15–25 ea** | [xtool.com → K9 Rectangle (1pc)](https://www.xtool.com/products/k9-rectangle-crystal-1pcs) |
| **K9 Crystal Ball Inner Engraved Kit** (includes fixture + ball) | **~$30–50** | [xtool.com → K9 Ball Kit](https://www.xtool.com/products/k9-crystal-ball-inner-engraved-kit) |
| **Raspberry Pi 5** (4GB) | **~$60–80** | [raspberrypi.com](https://www.raspberrypi.com) · Micro Center · PiShop.us |
| **Pi HQ Camera** (IMX477, 12MP) | **~$55–65** | [Arducam kit — Amazon](https://www.amazon.com/Arducam-IMX477-Camera-Raspberry-Compatible/dp/B0D95VWCV6) |
| **JGS2 fused silica blanks** (production, 5–10pk) | **$40–80** | [eBay JGS2 discs](https://www.ebay.com/itm/274136028727) · [Amazon optical-grade](https://www.amazon.com/Optical-Grade-Fused-Silica-Wafer-Thickness/dp/B0G7VRNT66) |
| **Motorized XY stage** | **$70–300** | Amazon: search "PT-XY100 motorized microscope stage" |
| **2020 extrusion frame + misc** | **~$50** | Any Amazon extrusion kit |

**Total: ~$4,600–$5,000** (mostly the xTool)

> **Inner engraving lens:** The F2 Ultra UV ships with a dedicated inner engraving lens in the box — no extra purchase needed. Swap it before running inner/subsurface mode. See the [xTool inner engraving setup guide](https://support.xtool.com/article/2708).

> **Which glass to buy first?**
> Start with the **K9 rectangle crystal** (100×50×50mm, ~$15–25). It's optically matched to the F2 Ultra UV and engraves cleanly out of the box. Use it to dial in power/speed/focus. Then move to cheaper JGS2 fused silica blanks for production runs.

---

## xTool F2 Ultra — Specs & Settings

| Spec | Value |
|------|-------|
| Laser | 5W UV 355 nm (cold processing — no burning or surface damage) |
| Spot size | **0.02 mm (20 µm)** |
| Max engraving speed | **15,000 mm/s** |
| Inner engraving area | **70 × 70 mm** (swap to dedicated inner lens first) |
| Max material height | 150 mm (Z axis) |
| Software | **xTool Studio** (free) |
| Input for 2D dotting | PNG, JPG, BMP, SVG — load our dot-grid PNG directly |
| Input for 3D inner | STL, OBJ, AMF, 3MF, GLB, PLY — load our voxel STL directly |

### Starting settings for fused silica / K9 (tune from here)

| Parameter | 2D flat grid | 3D voxel STL |
|-----------|-------------|--------------|
| Power | 80% | 60–70% |
| Speed | 300–500 mm/s | 500 mm/s |
| Dot duration | 50–100 µs | 50 µs |
| Z depth | 1 mm below surface | auto per layer |
| Mode | Dotting / Bitmap | Inner Engraving (3D) |

**Dial in on the included K9 test block first.** Correct dots look like bright white scattering points when lit from the side — not cracks, not cloudy regions. If dots crack the glass, reduce power or increase speed.

### About the AI Composer (AImake / Atomm)

xTool Studio includes an AI model generator (via Atomm) that converts a **photo → 3D portrait mesh** for artistic crystal engravings (the "grandma in a glass cube" product). It takes JPG/PNG/WEBP images and outputs artistic 3D models.

**It cannot encode arbitrary files or binary data.** Our encoder and decoder handle that. The two tools are complementary, not interchangeable.

---

## Storage Density

### 2D Flat Mode (encode_ssle.py → PNG → xTool dotting mode)

| Dot pitch | Grid (70×70mm area) | Raw capacity | After RS ECC (ECC=20) |
|-----------|--------------------|--------------|-----------------------|
| 200 µm (safe starter) | 350×350 | ~15 KB | ~14 KB |
| 100 µm (recommended) | 700×700 | ~61 KB | **~56 KB** |
| 75 µm | 933×933 | ~109 KB | ~100 KB |
| 50 µm (aggressive) | 1400×1400 | ~245 KB | ~224 KB |

### 3D Volumetric Mode (encode_ssle_3d.py → STL → xTool inner engraving)

| Layers | 100µm XY pitch | Usable after ECC |
|--------|----------------|-----------------|
| 5 | 700×700×5 | **~280 KB** |
| 10 | 700×700×10 | **~560 KB** |
| 20 | 700×700×20 | **~1.1 MB** |

> Run `python3 encode_ssle_3d.py --capacity` to calculate exact capacity for your settings.
> Run `python3 test_pipeline.py --density` for the full 2D density table.

---

## Software Setup

**On your Pi (reader hardware):**
```bash
git clone https://github.com/mrdulasolutions/5d-glass-reader.git
cd 5d-glass-reader
bash setup.sh
```

**On your laptop/Mac (encoder — no Pi needed):**
```bash
git clone https://github.com/mrdulasolutions/5d-glass-reader.git
cd 5d-glass-reader
pip install -r requirements.txt
```

**Verify the full software pipeline (no hardware needed):**
```bash
python3 test_pipeline.py                    # clean round-trip
python3 test_pipeline.py --noise 100        # test RS recovery with 100 bit-flips
python3 test_pipeline.py --density          # print density table
```

---

## End-to-End Workflow

### 2D (flat dot grid) — simplest, recommended for v0.1 hardware

**Step 1 — Encode:**
```bash
python3 encode_ssle.py myfile.txt
# → myfile_grid.png  +  prints xTool Studio import settings
```

**Step 2 — Engrave:**
- Open **xTool Studio** → New Project → Import `myfile_grid.png`
- Set physical size to the mm value printed by the encoder
- Mode: **Dotting** (bitmap inner engraving)
- Swap to inner engraving lens, set Z depth ~1mm below surface
- Engrave onto K9 crystal or fused silica blank

**Step 3 — Scan:**
```bash
./run_reader.sh
# prompts: place disc under camera → press Enter → captures + decodes
```

**Step 4 — Decode output:**
```
output/myfile.txt   ← your original file, recovered from glass
```

Pass `--cols`/`--rows`/`--ecc` to `decode_ssle.py` if you used non-default encoder settings.

---

### Full disc raster scan (motorized stage)

```bash
python3 scan_disc.py --width 20 --height 20 --step 0.5
# scans 20×20mm area in 0.5mm steps → saves raw_scattering/scan_X_Y.png tiles
# then decode each tile: python3 decode_ssle.py raw_scattering/scan_0.00_0.00.png
```

Test without hardware:
```bash
python3 scan_disc.py --sim
python3 stage_control.py --sim --x 10 --y 10
```

---

## 3D Volumetric Mode (v0.3)

Encodes data across multiple Z depths → outputs an **STL** → load directly into xTool Studio inner engraving. Capacity scales linearly with number of layers.

**Encode:**
```bash
python3 encode_ssle_3d.py myfile.txt --layers 5
# → myfile_voxel.stl  +  prints xTool Studio import settings

python3 encode_ssle_3d.py --capacity --layers 10   # check capacity before encoding
```

**Engrave:**
- xTool Studio → Import `myfile_voxel.stl` → Inner Engraving (3D mode)
- Scale model to fit 70×70mm area — Studio handles Z layer sequencing automatically

**Decode** (requires per-layer captures at each Z depth):
```bash
# Capture one image per Z depth → save as layers/layer_00.png, layer_01.png, ...
python3 decode_ssle_3d.py layers/ --layers 5
# → output/myfile.txt
```

> **Reader hardware for 3D:** Z-adjustable focus required — motorized Z stage or liquid lens module. Coming in v0.3 hardware build. The encoder and decoder are fully implemented now.

---

## File Structure

```
5d-glass-reader/
│
│  ── Encoding (run on laptop/Mac) ──
├── encode_ssle.py         # any file → 2D dot-grid PNG  (xTool dotting mode)
├── encode_ssle_3d.py      # any file → 3D voxel STL     (xTool inner engraving 3D)
│
│  ── Decoding (run on Pi) ──
├── capture_scattering.py  # capture glass disc image via Pi HQ camera
├── decode_ssle.py         # 2D dot-grid PNG → original file  (RS ECC + fiducials)
├── decode_ssle_3d.py      # multi-layer images → original file (3D RS decode)
├── run_reader.sh          # one-shot: capture + 2D decode
│
│  ── Stage control ──
├── stage_control.py       # XY stepper driver (PT-XY100 + RPi.GPIO, sim mode)
├── scan_disc.py           # automated boustrophedon raster scan + manifest
│
│  ── Testing & verification ──
├── test_pipeline.py       # full encode→decode round-trip (no hardware needed)
│                          # --noise N: RS recovery test  --density: capacity table
│
│  ── Setup & config ──
├── setup.sh               # one-time Pi install script
├── requirements.txt       # Python deps (picamera2, opencv, numpy, reedsolo, ...)
│
│  ── Project docs ──
├── README.md              # this file
├── ETHOS.md               # why we are building this
├── CONTRIBUTING.md        # how to join
├── LICENSE                # MIT
│
│  ── Runtime dirs (gitignored) ──
├── raw_scattering/        # captured images
├── raw_scattering/layers/ # per-Z-depth layer images for 3D decode
└── output/                # decoded files
```

---

## Roadmap

| Version | Status | What |
|---------|--------|------|
| v0.1 | ✅ shipped | Manual capture, dot detection, basic decode |
| v0.2 | ✅ shipped | Encoder + RS ECC + motorized XY stage + raster scan + pipeline test |
| v0.3 | 🔨 in progress | 3D STL encoder ✅ · 3D decoder ✅ · Z-stage hardware · image tile stitcher |
| v0.4 | planned | Higher dot density (50µm) · adaptive threshold · better fiducial detection |
| v1.0 | planned | Full SSLE read/write pipeline — turnkey on Pi 5 |
| v2.0 | future | True 5D upgrade: femtosecond birefringence encoding (polarization + retardance) |

---

Built live with Grok + Claude. No gatekeepers. Only build.

**⭐ Star this repo if you're in.**

See [ETHOS.md](ETHOS.md) · [CONTRIBUTING.md](CONTRIBUTING.md) · [LICENSE](LICENSE)
