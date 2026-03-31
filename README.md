# 5D Glass Eternal Drive — Phase 1 Reader (Indie 2026 Build)
**mrdulasolutions/5d-glass-reader**

USB polarized microscope reader for real SPhotonix-style 5D silica crystals.
Decodes birefringence (retardance + slow-axis orientation) using crossed polarizers + Raspberry Pi HQ camera + ppm_library.

**Hardware:** Pi 5 + HQ Camera + linear polarizers + motorized XY stage (stage control coming in v0.2).

**Status:** v0.1 — manual polarizer rotation → full retardance + orientation map → basic 5D decode ready.
We are building the first indie eternal drive reader.

---

## Hardware Setup

| Component | Notes |
|-----------|-------|
| Raspberry Pi 5 | 4GB+ recommended |
| Pi HQ Camera (12MP) | IMX477 sensor |
| 2× Linear polarizers | One fixed (polarizer), one rotatable (analyzer) |
| USB polarized microscope | Or optical bench with above polarizers |
| Motorized XY stage | Optional in v0.1 — coming in v0.2 |

---

## Install (on Pi)

```bash
git clone git@github.com:mrdulasolutions/5d-glass-reader.git
cd 5d-glass-reader
bash setup.sh
```

---

## Usage

```bash
./run_reader.sh
```

This will:
1. Prompt you to rotate the analyzer to **0°, 45°, 90°, 135°** (press Enter at each)
2. Capture a polarized image at each angle
3. Run birefringence decode via ppm_library
4. Save retardance map to `output/retardance_map.png`

---

## File Structure

```
5d-glass-reader/
├── capture_polarized.py   # Step 1: capture 4 polarizer angles
├── decode_5d.py           # Step 2: birefringence decode + 5D map
├── run_reader.sh          # Runs both steps in sequence
├── setup.sh               # One-time Pi install script
├── requirements.txt       # Cross-platform Python deps
├── requirements-pi.txt    # Pi-only deps (adds RPi.GPIO)
├── raw_polarized/         # Captured images (gitignored)
├── output/                # Decoded maps (gitignored)
└── calibration/           # Saved calibration data (gitignored)
```

---

## Roadmap

- **v0.1** (now) — manual polarizer rotation, single voxel capture, basic decode
- **v0.2** — servo-controlled polarizer rotation, motorized XY stage raster scan
- **v0.3** — full disc raster scan + 3D voxel reconstruction
- **v1.0** — complete 5D read pipeline (x, y, z, retardance, orientation)
