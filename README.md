# 5D Glass Eternal Drive — Phase 1 Reader (COTS SSLE Edition)
**mrdulasolutions** indie hacker build — March 2026

Fully commercial off-the-shelf subsurface laser engraving (SSLE) glass drive.
Writer: xTool F2 Ultra UV 5W (or equivalent COTS UV laser).
Reader: Raspberry Pi 5 + HQ Camera + motorized XY stage decodes scattering dots → binary file.

Status: v0.1 SSLE — generate dot grid → engrave with xTool → scan & decode back to file.
This is the world's first fully indie COTS glass memory drive.

Next: error correction, higher density, motorized full-disc scan, then true 5D upgrade.

---

## Hardware Setup

| Component | Notes |
|-----------|-------|
| Raspberry Pi 5 | 4GB+ recommended |
| Pi HQ Camera (12MP) | IMX477 sensor |
| xTool F2 Ultra UV 5W | Or any COTS UV laser engraver |
| Glass disc / slide | Standard borosilicate or optical glass |
| Motorized XY stage | Optional in v0.1 — coming in v0.2 |

---

## Install (on Pi)

```bash
git clone https://github.com/mrdulasolutions/5d-glass-reader.git
cd 5d-glass-reader
bash setup.sh
```

---

## Usage

```bash
./run_reader.sh
```

This will:
1. Position the glass disc under the camera and press Enter to capture
2. Detect scattering dots via OpenCV blob detection
3. Decode dots → binary file saved to `output/decoded_file.bin`

---

## File Structure

```
5d-glass-reader/
├── capture_scattering.py  # Step 1: capture glass disc image
├── decode_ssle.py         # Step 2: detect dots + decode to binary
├── run_reader.sh          # Runs both steps in sequence
├── setup.sh               # One-time Pi install script
├── requirements.txt       # Python deps
├── raw_scattering/        # Captured images (gitignored)
└── output/                # Decoded files (gitignored)
```

---

## Roadmap

- **v0.1** (now) — manual capture, dot detection, basic binary decode
- **v0.2** — motorized XY stage raster scan, perspective correction
- **v0.3** — error correction (Reed-Solomon), higher dot density
- **v1.0** — full SSLE read/write pipeline
- **v2.0** — true 5D upgrade (birefringence encoding)
