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

## xTool F2 Ultra — Inner Engraving Specs (March 2026)

| Spec | Value |
|------|-------|
| Laser | 5W UV 355 nm (cold processing — no burning) |
| Spot size | **0.02 mm (20 µm)** |
| Max speed | **15,000 mm/s** |
| Inner engraving area | **70 × 70 mm** (dedicated lens required — included) |
| Software mode | **Dotting mode** — feed it our dot-grid PNG directly |
| Best test media | K9 crystal (included) → then move to fused silica JGS1/JGS2 |

**Starting settings for fused silica:** ~60% power, 500–1000 mm/s, single pass.
Dial in on the included K9 test block first. Dots should be bright white scattering points when lit from the side — not cracks or cloudy regions.

---

## Storage Density (70×70 mm inner area)

| Dot pitch | Grid | Raw capacity | After RS ECC (~8.5% overhead) |
|-----------|------|-------------|-------------------------------|
| 200 µm (safe starter) | 350×350 | ~15 KB | ~14 KB |
| 100 µm (recommended) | 700×700 | ~61 KB | ~56 KB |
| 75 µm | 933×933 | ~109 KB | ~100 KB |
| 50 µm (aggressive) | 1400×1400 | ~245 KB | ~224 KB |

**Run `python3 test_pipeline.py --density` to see the full table.**
The encoder prints exact capacity for your chosen grid before you engrave a single dot.

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

**Step 0 — Verify the pipeline (no hardware needed):**
```bash
python3 test_pipeline.py               # clean round-trip test
python3 test_pipeline.py --noise 100   # inject 100 bit flips → test RS recovery
python3 test_pipeline.py --density     # print density table
```

**Step 1 — Encode any file to a dot-grid PNG:**
```bash
python3 encode_ssle.py myfile.txt
# → outputs myfile_grid.png + prints xTool settings
```

**Step 2 — Engrave:**
Load `myfile_grid.png` into xTool software → subsurface mode → engrave into fused silica blank.
The encoder prints the exact physical size and power/speed settings to use.

**Step 3 — Scan & decode:**
```bash
./run_reader.sh
# → captures disc → detects dots → outputs output/myfile.txt
```
Pass `--cols` / `--rows` to match what you used during encoding (default 200×200).

**Grid capacity (default 200×200):**
~4.5 KB per disc. Use `--cols 400 --rows 400` for ~18 KB. The encoder tells you exactly.

**CRC32 verification is built in** — you'll know immediately if the decode was clean.

---

## File Structure

```
5d-glass-reader/
├── encode_ssle.py         # Step 0: any file → xTool dot-grid PNG (run on laptop)
├── capture_scattering.py  # Step 1: capture glass disc image (run on Pi)
├── decode_ssle.py         # Step 2: detect dots + RS decode back to file (run on Pi)
├── scan_disc.py           # Auto raster scan — full disc via motorized stage
├── stage_control.py       # XY stepper stage driver (PT-XY100 + RPi.GPIO)
├── test_pipeline.py       # Software round-trip test — verify before engraving
├── run_reader.sh          # Runs capture + decode in sequence
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

- **v0.1** — manual capture, dot detection, basic binary decode
- **v0.2** ✅ (now) — encoder + Reed-Solomon ECC + motorized XY stage + raster scan
- **v0.3** — image stitch from multi-tile scan, higher dot density
- **v1.0** — full SSLE read/write pipeline
- **v2.0** — true 5D upgrade (femtosecond birefringence encoding)

---

Built live with Grok. No gatekeepers. Only build.

**Star this repo if you're in.**

See [ETHOS.md](ETHOS.md) for why this exists.
See [CONTRIBUTING.md](CONTRIBUTING.md) to join the build.
