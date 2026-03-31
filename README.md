# 5D Glass Eternal Drive — COTS SSLE Edition
**mrdulasolutions** indie hacker build — March 2026

World's first fully commercial-off-the-shelf subsurface laser engraving glass memory drive + reader.

**Writer**: xTool F2 Ultra UV 5W (engraves dots inside fused silica)
**Reader**: Raspberry Pi 5 + HQ Camera + cheap motorized XY stage
**Media**: Cheap fused silica discs (~$10–50 each)
**Status**: v0.1 — file → dot grid → engrave → scan → decode back to binary file

---

## Total Cost (March 2026)

| Item | Price | Link |
|------|-------|------|
| xTool F2 Ultra UV 5W (standalone) | **$4,249** | [xtool.com](https://www.xtool.com/products/xtool-f2-ultra-uv-5w-uv-laser-engraver) |
| Raspberry Pi 5 + HQ Camera kit | **~$120–$150** | [Arducam IMX477 on Amazon](https://www.amazon.com/Arducam-IMX477-Camera-Raspberry-Compatible/dp/B0D95VWCV6) or RaspberryPi.com resellers |
| Fused silica blanks (5–10 pack) | **$40–$80** | [eBay JGS2 discs](https://www.ebay.com/itm/274136028727) or [Amazon optical-grade packs](https://www.amazon.com/Optical-Grade-Fused-Silica-Wafer-Thickness/dp/B0G7VRNT66) |
| Cheap motorized XY stage | **$70–$300** | Search Amazon: "PT-XY100 motorized microscope stage" |
| Frame / 2020 extrusion + misc | **~$50** | Any Amazon extrusion kit |

**Grand total for working drive + reader: ~$5,000–$6,000**

---

## Hardware Setup (Step-by-Step)

1. Buy everything above.
2. Assemble Pi 5 + HQ Camera (CS-mount lens pointed down toward stage).
3. Mount camera + stage on 2020 extrusion or 3D-printed frame (files coming in v0.2).
4. Plug motorized stage into Pi GPIO (code coming in v0.2).
5. Install xTool software on your laptop → connect F2 Ultra via USB.

---

## Software Setup (5 minutes)

```bash
git clone https://github.com/mrdulasolutions/5d-glass-reader.git
cd 5d-glass-reader
bash setup.sh
```

Or manually:

```bash
pip install -r requirements.txt
chmod +x run_reader.sh
```

---

## How to Use (End-to-End Workflow)

1. **Encode** — Run the encoder (coming in v0.2) → generates PNG dot grid from any file.
2. **Engrave** — Load PNG into xTool software → engrave into fused silica blank (subsurface mode).
3. **Capture** — Place engraved disc under Pi camera → `./run_reader.sh`
4. **Decode** → captures image → detects scattering dots → outputs `output/decoded_file.bin`

---

## File Structure

```
5d-glass-reader/
├── capture_scattering.py  # Step 1: capture glass disc image
├── decode_ssle.py         # Step 2: detect dots + decode to binary
├── run_reader.sh          # Runs both steps in sequence
├── setup.sh               # One-time Pi install script
├── requirements.txt       # Python deps
├── ETHOS.md               # Why we are building this
├── CONTRIBUTING.md        # How to contribute
├── LICENSE                # MIT
├── raw_scattering/        # Captured images (gitignored)
└── output/                # Decoded files (gitignored)
```

---

## Roadmap

- **v0.1** (now) — manual capture, dot detection, placeholder binary decode
- **v0.2** — encoder script (file → xTool dot-grid PNG) + motorized raster scan
- **v0.3** — Reed-Solomon error correction + higher dot density
- **v1.0** — full SSLE read/write pipeline
- **v2.0** — true 5D upgrade (femtosecond birefringence encoding)

---

Built live with Grok. No gatekeepers. Only build.

**Star this repo if you're in.**

See [ETHOS.md](ETHOS.md) for why this exists.
See [CONTRIBUTING.md](CONTRIBUTING.md) to join the build.
