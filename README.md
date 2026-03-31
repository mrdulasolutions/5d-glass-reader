# 5D Glass Eternal Drive — COTS SSLE Edition
**mrdulasolutions/5d-glass-reader** · indie hacker build · March 2026

World's first fully commercial-off-the-shelf subsurface laser engraving (SSLE) glass memory drive + reader.
No femtosecond lasers. No lab. No gatekeepers. Just a UV laser and some fused silica.

**Writer**: xTool F2 Ultra UV 5W — engraves dots *inside* glass
**Reader**: xTool F2 Ultra (same machine!) · USB microscope · or Raspberry Pi 5
**Media**: K9 optical crystal (calibration) · JGS2 fused silica (production)
**Status**: v0.3 — True 5D encoding (dot size = 5th dimension), full encode → engrave → read pipeline, three reader paths, RS ECC

---

## Table of Contents
1. [The Core Idea](#the-core-idea)
2. [Why It's True 5D](#why-its-true-5d)
3. [Hardware & Cost](#hardware--cost)
4. [xTool F2 Ultra — Specs & Settings](#xtool-f2-ultra--specs--settings)
5. [The Three Reader Paths](#the-three-reader-paths)
6. [Full Workflow](#full-workflow)
7. [Storage Density](#storage-density)
8. [3D Volumetric Mode](#3d-volumetric-mode)
9. [Software Setup](#software-setup)
10. [File Structure](#file-structure)
11. [Roadmap](#roadmap)

---

## The Core Idea

```
WRITE                              READ (reverse — same machine)
─────                              ──────────────────────────────
Your file                          Load K9 back into F2 Ultra
    ↓                                  ↓
encode_ssle_3d.py → .stl          xTool Studio → Snapshot
    ↓                                  ↓
xTool Studio → import STL         capture_scattering.py --source xtool
    ↓                                  ↓
F2 Ultra engraves K9 crystal      decode_ssle.py → original file ✅
```

**The xTool F2 Ultra is both writer AND reader.** Its dual 48MP cameras can snapshot the engraved dot pattern. Feed that image to `decode_ssle.py`. No extra hardware required for a basic read. The Raspberry Pi path adds automated scanning for large discs.

---

## Why It's True 5D

Most "5D glass" marketing counts 3 spatial dimensions + polarization state + retardance — requiring femtosecond lasers costing $100K+. We achieve true 5D with a $4,249 COTS machine:

| Dimension | What it is | How we use it |
|-----------|-----------|---------------|
| **D1** | X position | Column in dot grid |
| **D2** | Y position | Row in dot grid |
| **D3** | Z depth | Layer in 3D voxel grid (inner engraving) |
| **D4** | Dot presence | Engrave here or not (the 1/0 bit) |
| **D5** | **Dot SIZE** | Pixel brightness → laser dwell time → physical bubble size |

**D5 is real, physical, and readable.** xTool's grayscale inner engraving mode maps pixel brightness directly to laser dwell time — darker pixel = longer dwell = more energy deposited = larger scattering bubble. Our 4-level encoding uses this to pack **2 bits per dot position** instead of 1, doubling capacity in the same physical grid area.

```
Pixel value  →  Laser dwell  →  Bubble size  →  Encoded value
   255 (white)    no fire          none           00  (level 0)
   192 (gray)     short dwell      small          01  (level 1)
   128 (gray)     medium dwell     medium         10  (level 2)
     0 (black)    full dwell       large          11  (level 3)
```

**2D flat grid + D5:** 2 bits/position × same grid area = 2× the data of binary encoding.
**3D voxel grid + D5:** Add Z-depth (D3) for another N× multiplier. 10 layers × 2 bits = 20× binary 2D.

---

## Hardware & Cost

| Component | Price (Mar 2026) | Buy Direct |
|-----------|-----------------|------------|
| **xTool F2 Ultra UV 5W** ← writer + reader | **$4,249** | [xtool.com → F2 Ultra UV](https://www.xtool.com/products/xtool-f2-ultra-uv-5w-uv-laser-engraver) |
| **K9 Rectangle Crystal** (100×50×50mm blank) | **~$15–25 ea** | [xtool.com → K9 Rectangle (1pc)](https://www.xtool.com/products/k9-rectangle-crystal-1pcs) |
| **K9 Crystal Ball Inner Engraved Kit** | **~$30–50** | [xtool.com → K9 Ball Kit](https://www.xtool.com/products/k9-crystal-ball-inner-engraved-kit) |
| **JGS2 fused silica blanks** (5–10pk, production) | **$40–80** | [eBay JGS2 discs](https://www.ebay.com/itm/274136028727) · [Amazon optical-grade](https://www.amazon.com/Optical-Grade-Fused-Silica-Wafer-Thickness/dp/B0G7VRNT66) |
| *(optional)* USB digital microscope | **$30–100** | Amazon: "USB digital microscope 1000x" |
| *(optional)* Raspberry Pi 5 (4GB) | **~$60–80** | [raspberrypi.com](https://www.raspberrypi.com) · Micro Center |
| *(optional)* Pi HQ Camera (IMX477) | **~$55–65** | [Arducam kit — Amazon](https://www.amazon.com/Arducam-IMX477-Camera-Raspberry-Compatible/dp/B0D95VWCV6) |
| *(optional)* Motorized XY stage | **$70–300** | Amazon: "PT-XY100 motorized microscope stage" |
| *(optional)* 2020 extrusion frame | **~$50** | Any Amazon extrusion kit |

**Minimum to start: ~$4,300** (xTool + K9 crystals — that's it)
**Full automated rig: ~$4,800–$5,000**

> **Inner engraving lens ships in the box** — no extra purchase. Swap it before inner/subsurface mode.
> Setup guide: [support.xtool.com/article/2708](https://support.xtool.com/article/2708)

---

## xTool F2 Ultra — Specs & Settings

| Spec | Value |
|------|-------|
| Laser | 5W UV 355 nm — cold processing, no surface burning |
| Spot size | **0.02 mm (20 µm)** |
| Max engraving speed | **15,000 mm/s** |
| Inner engraving area | **70 × 70 mm** (dedicated inner lens, included) |
| Max material height (Z) | 150 mm |
| Built-in cameras | **Dual 48MP** — used for alignment AND reading |
| Software | **xTool Studio v1.6.6** — [⬇ Download free](https://www.xtool.com/pages/software) (Win / macOS-Intel / macOS-M) |
| 2D input (inner engraving) | PNG, JPG, BMP, SVG — load our dot-grid PNG in **Grayscale mode** |
| 3D input (inner engraving) | **STL, OBJ, AMF, 3MF, GLB, PLY** — load our voxel STL directly |

> **Required reading before first engrave:**
> - [Course 279 — Getting Started with F2 Ultra UV](https://support.xtool.com/academy/course?id=279)
> - [Course 280 — F2 Ultra UV Essentials: Software & Materials](https://support.xtool.com/academy/course?id=280)
> - [Course 281 — F2 Ultra UV Inner Engraving: Skills and Best Practices](https://support.xtool.com/academy/course?id=281)
> - [Article 2708 — Start Inner Engraving (lens swap guide)](https://support.xtool.com/article/2708)

### Engrave settings (start here, tune for your glass)

| Setting | 2D PNG (True 5D grayscale) | 3D STL inner (per pass) |
|---------|---------------------------|-------------------------|
| Power | 70–80% | L1: 50–60% · L2: 65–75% · L3: 80–90% |
| Speed | 300–500 mm/s | 500 mm/s |
| Dot duration | 100–300 µs | 100–200 µs (Dotting sub-mode) |
| Z depth | 1 mm below surface | auto per layer |
| Studio mode | **Grayscale** inner engraving | Inner Engraving (3D) → **Dotting** |

**Start on K9 crystal** (optically ideal). Correct dots = bright white scattering points lit from the side. Cracks or cloudy regions = reduce power/dot duration.

> **Why Grayscale mode for 2D inner engraving?**
> xTool's docs say "don't use Grayscale for photos" — that warning is about visual quality for portraits (Jarvis dithering looks better for natural images). For *data encoding*, Grayscale mode is exactly right: it maps pixel brightness directly to laser dwell time → physical bubble size (D5). Our encoder outputs precise gray values (255/192/128/0), not photos. Do NOT use Bitmap/Jarvis/Dither modes — they destroy the gray levels and collapse D5 to binary.

### About the AI Composer (AImake / Atomm)

xTool Studio includes Atomm's AI 3D Model Generator — converts a **photo → artistic 3D portrait mesh** for crystal souvenirs. Input: JPG/PNG/WEBP. Output: beautiful 3D model of a face.

It **cannot encode arbitrary binary files** and has no concept of data storage. Our encoder handles that. The two tools are complementary — Atomm for art, our encoder for data.

---

## The Three Reader Paths

### ⚡ FASTEST + EASIEST — xTool F2 Ultra (same machine)
*No extra hardware. The machine you already have.*

```
Load engraved K9 back into F2 Ultra
    → xTool Studio: Camera icon → Snapshot → Save image
    → python3 capture_scattering.py --source xtool --file snapshot.png
    → python3 decode_ssle.py
```

The F2 Ultra's **dual 48MP cameras** can image the engraved dot pattern.
Pro tip: shine a flashlight at a low angle on the crystal before snapping —
scattering dots glow bright white under raking light.

**Hardware needed:** Nothing beyond what you already bought.
**Best for:** Quick verify, low-volume reads, single disc.

---

### 💡 EASIEST standalone reader — USB Digital Microscope (~$30)
*Works on any laptop. No Pi, no GPIO, no configuration.*

```
Plug USB microscope into laptop
Position engraved disc under microscope
    → python3 capture_scattering.py --source usb
    → python3 decode_ssle.py
```

Any $30–100 USB digital microscope from Amazon resolves 100µm dots fine.
Run `decode_ssle.py` directly on your Mac or Windows machine.

**Hardware needed:** USB microscope, laptop.
**Best for:** Desktop read station, demos, development.

---

### 🎯 MOST ACCURATE — Raspberry Pi + HQ Camera + Motorized Stage
*Automated full-disc raster scan. Best image quality. Most repeatable.*

```
Pi HQ Camera + motorized XY stage over disc
    → python3 scan_disc.py --width 20 --height 20 --step 0.5
    → python3 decode_ssle.py raw_scattering/scan_0.00_0.00.png
```

Use `stage_control.py` for XY movement. Captures every grid zone automatically.
Best for large discs, high-density grids, or production workflows.

**Hardware needed:** Pi 5 + HQ Camera + motorized XY stage + frame.
**Best for:** High-density grids, full-disc scanning, production.

---

## Full Workflow

### Write (encode → STL → engrave)

**Step 1 — Encode your file:**
```bash
# True 5D — 3D voxel STL (recommended — highest capacity)
python3 encode_ssle_3d.py myfile.txt --layers 5
# → myfile_voxel_L1_small.stl   (low power pass)
#   myfile_voxel_L2_medium.stl  (medium power pass)
#   myfile_voxel_L3_large.stl   (full power pass)
#   + exact xTool Studio settings printed

# True 5D — 2D flat PNG (simpler, great for smaller files)
python3 encode_ssle.py myfile.txt
# → myfile_5d.png  (4-level grayscale)  +  exact settings
```

**Step 2 — Engrave in xTool Studio:**
- Open **xTool Studio** → New Project → swap to inner engraving lens
- **For 2D PNG:** Import `myfile_5d.png` → **Grayscale** mode → set size from encoder output → Engrave
  - ⚠️ Do NOT use bitmap/dotting mode — it crushes gray levels and destroys D5
- **For 3D STL (3 passes):** Import each STL file in order (L1 → L2 → L3)
  - Each gets different power (50-60% / 65-75% / 80-90%)
  - Do NOT move the crystal between passes — Z registration is critical
- Place K9 crystal in machine → Engrave

---

### Read (reverse — load K9 back into F2)

**Option A — xTool F2 Ultra camera (fastest + easiest):**
```bash
# 1. Load engraved K9 back into F2 Ultra
# 2. xTool Studio → Camera icon → Snapshot → save file
python3 capture_scattering.py --source xtool --file snapshot.png
python3 decode_ssle.py
```

**Option B — USB microscope:**
```bash
python3 capture_scattering.py --source usb
python3 decode_ssle.py
```

**Option C — Pi HQ Camera (most accurate):**
```bash
./run_reader.sh
```

**One-liner for all paths:**
```bash
# A/B/C: python3 decode_ssle.py raw_scattering/capture.png --cols 200 --rows 200
#        python3 decode_ssle.py raw_scattering/capture.png --cols 200 --rows 200 --levels 4
# (--levels 4 is default for True 5D; use --levels 2 for legacy binary grids)
```

---

### Verify before engraving (no hardware needed)
```bash
python3 test_pipeline.py               # clean software round-trip
python3 test_pipeline.py --noise 100   # test RS error recovery
python3 test_pipeline.py --density     # print capacity table
```

---

## Storage Density

---

### K9 Rectangle Crystal — 100×50×50 mm (the standard blank)

**Usable inner engraving area: 50×50 mm XY · up to 48 mm Z depth**

#### 2D flat (single layer) — `encode_ssle.py`

| Dot pitch | Grid | Binary (1 bit/dot) | **True 5D (2 bits/dot)** | Encoder command |
|-----------|------|--------------------|--------------------------|-----------------|
| 200 µm (safe) | 250×250 | ~6 KB | **~13 KB** | `--cols 250 --rows 250` |
| **100 µm (recommended)** | 500×500 | ~27 KB | **~54 KB** | `--cols 500 --rows 500` |
| 75 µm | 667×667 | ~49 KB | **~98 KB** | `--cols 667 --rows 667` |
| 50 µm (aggressive) | 1000×1000 | ~111 KB | **~222 KB** | `--cols 1000 --rows 1000` |

#### 3D volumetric — `encode_ssle_3d.py` · 100 µm XY · 0.5 mm z-pitch · 500×500 grid

| Layers | Z depth used | Binary (1 bit/voxel) | **True 5D (2 bits/voxel)** | Encoder command |
|--------|-------------|----------------------|----------------------------|-----------------|
| 5 | 2.5 mm | ~137 KB | **~270 KB** | `--cols 500 --rows 500 --layers 5` |
| 10 | 5 mm | ~274 KB | **~540 KB** | `--cols 500 --rows 500 --layers 10` |
| 20 | 10 mm | ~548 KB | **~1.1 MB** | `--cols 500 --rows 500 --layers 20` |
| 40 | 20 mm | ~1.1 MB | **~2.2 MB** | `--cols 500 --rows 500 --layers 40` |
| **80** | **40 mm** | **~2.2 MB** | **~4.3 MB** | `--cols 500 --rows 500 --layers 80` |
| 96 (max) | 48 mm | ~2.6 MB | **~5.2 MB** | `--cols 500 --rows 500 --layers 96` |

> All values are usable capacity after RS ECC overhead (default `--ecc 20`).
> Higher layer counts require Z-stage or per-layer manual focus during readback.

```bash
# Print exact capacity for your K9 config:
python3 encode_ssle_3d.py --capacity --cols 500 --rows 500 --layers 10 --levels 4
```

---

### Machine Maximum — 70×70 mm inner engraving area

For reference: if you fill the full xTool F2 Ultra inner area with a larger crystal (JGS2 production runs).

#### 2D flat PNG (encode_ssle.py → xTool Grayscale mode)

| Dot pitch | Grid in 70×70mm | Binary (1 bit/dot) | **True 5D (2 bits/dot)** |
|-----------|----------------|---------------------|--------------------------|
| 200 µm (safe starter) | 350×350 | ~7 KB | **~14 KB** |
| **100 µm (recommended)** | 700×700 | ~28 KB | **~56 KB** |
| 75 µm | 933×933 | ~50 KB | **~100 KB** |
| 50 µm (aggressive) | 1400×1400 | ~112 KB | **~224 KB** |

> **xTool mode for True 5D:** use **Grayscale** inner engraving (NOT bitmap/dotting mode).
> Bitmap mode crushes gray values to pure black/white — you lose D5 entirely.

#### 3D voxel STL (encode_ssle_3d.py → xTool inner engraving 3D)

| Layers | 100µm XY, 70×70mm | Binary (1 bit/voxel) | **True 5D (2 bits/voxel)** |
|--------|---------------------|----------------------|----------------------------|
| 5 layers | 700×700×5 | ~140 KB | **~280 KB** |
| 10 layers | 700×700×10 | ~280 KB | **~560 KB** |
| 20 layers | 700×700×20 | ~560 KB | **~1.1 MB** |

> True 5D 3D outputs **3 STL files** per encode (small/medium/large voxels).
> Engrave all 3 passes without moving the crystal. xTool Studio handles Z-layering per file.

```bash
python3 encode_ssle_3d.py --capacity --layers 10            # binary capacity
python3 encode_ssle_3d.py --capacity --layers 10 --levels 4 # True 5D capacity
```

---

## 3D Volumetric Mode

The F2 Ultra natively accepts STL for inner engraving — it fires the laser at each voxel's 3D coordinates automatically. Our encoder builds the STL; xTool Studio handles the Z-layering.

```bash
# True 5D — outputs 3 STL files (one per dot size level):
python3 encode_ssle_3d.py myfile.txt --layers 5
# → myfile_voxel_L1_small.stl   → import first,  power 50–60%
# → myfile_voxel_L2_medium.stl  → import second, power 65–75%
# → myfile_voxel_L3_large.stl   → import third,  power 80–90%
# In xTool Studio: Inner Engraving → Dotting sub-mode
# ⚠️  Do NOT move the crystal between the 3 passes

# Decode from per-layer images (one image per Z depth):
python3 decode_ssle_3d.py layers/ --layers 5
```

> **Z-focus for 3D reads:** Requires focus adjustment per layer. Use F2 Ultra's auto-focus (each snapshot at a different Z) or a motorized Z stage on the Pi rig.

---

## Software Setup

**Step 0 — Download xTool Studio** (required to engrave):
[⬇ xTool Studio v1.6.6 — Windows / macOS-Intel / macOS-M](https://www.xtool.com/pages/software) · Free

```bash
git clone https://github.com/mrdulasolutions/5d-glass-reader.git
cd 5d-glass-reader
bash setup.sh          # Pi  — installs all deps + creates dirs
# OR
pip install -r requirements.txt   # Mac/Windows laptop — encoder + decoder only
```

**Test the full pipeline (no hardware):**
```bash
python3 test_pipeline.py
```

---

## File Structure

```
5d-glass-reader/
│
│  ── Encoding (run on any machine) ──────────────────────────────────────
├── encode_ssle.py          2D: any file → dot-grid PNG  (xTool dotting mode)
├── encode_ssle_3d.py       3D: any file → voxel STL     (xTool inner 3D mode)
│
│  ── Capture (three paths — see The Three Reader Paths above) ───────────
├── capture_scattering.py   --source xtool ⚡ | usb 💡 | pi 🎯 | file
│
│  ── Decoding ────────────────────────────────────────────────────────────
├── decode_ssle.py          2D dot-grid → original file  (RS ECC + fiducials)
├── decode_ssle_3d.py       3D multi-layer → original file
├── run_reader.sh           one-shot: Pi capture + 2D decode
│
│  ── Stage / automated scanning ─────────────────────────────────────────
├── stage_control.py        XY stepper driver (PT-XY100, RPi.GPIO, sim mode)
├── scan_disc.py            automated boustrophedon raster scan + manifest
│
│  ── Verification ────────────────────────────────────────────────────────
├── test_pipeline.py        encode→decode round-trip  --noise --density
│
│  ── Setup ───────────────────────────────────────────────────────────────
├── setup.sh                one-time install (Pi)
├── requirements.txt        picamera2 · opencv · numpy · reedsolo · numpy-stl
│
│  ── Docs ────────────────────────────────────────────────────────────────
├── README.md               this file
├── ETHOS.md                why we are building this
├── CONTRIBUTING.md         how to join the build
└── LICENSE                 MIT
```

---

## Roadmap

| Version | Status | What |
|---------|--------|------|
| v0.1 | ✅ | Manual capture, dot detection, basic decode |
| v0.2 | ✅ | Encoder + RS ECC + motorized XY stage + raster scan + 3D STL encoder/decoder + three reader paths |
| v0.3 | ✅ | **True 5D encoding** — dot size as 5th dimension, 4-level grayscale, 2 bits/position, 2× capacity |
| v0.4 | 🔨 | Image tile stitcher · Z-stage for automated 3D reads · 50µm density validation |
| v0.5 | planned | Adaptive threshold · better fiducial detection (SIFT/ORB) |
| v1.0 | planned | Turnkey SSLE read/write on Pi 5 — one command, full disc |
| v2.0 | future | 6D: femtosecond birefringence (polarization + retardance) on top of SSLE |

---

Built live with Grok + Claude. No gatekeepers. Only build.

**⭐ Star this repo if you're in.**

[ETHOS.md](ETHOS.md) · [CONTRIBUTING.md](CONTRIBUTING.md) · [LICENSE](LICENSE)
