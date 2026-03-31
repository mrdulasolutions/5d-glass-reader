# How to Contribute (Indie Style)

1. Fork the repo.
2. Make your change (code, docs, 3D files, encoder improvements, whatever).
3. Open a PR with a clear title and one line: "why this helps the mission."
4. We merge fast if it works on real hardware.
5. No corporate-speak. Be direct. Be based.

---

## Biggest Needs Right Now (March 2026)

### Hardware
- **Z-stage / motorized Z focus** for multi-layer 3D reads (`decode_ssle_3d.py` is ready — needs the hardware capture side)
- **3D-printable frame** for Pi camera + XY stage (STL/OpenSCAD files)
- **Servo-controlled polarizer** (future v2.0 5D upgrade path)
- **Real-world xTool F2 Ultra settings** for JGS2 fused silica — what power/speed/Z actually works? Open an issue with your results.

### Software
- **Image tile stitcher** — combine `scan_disc.py` tiles into a single full-disc image for large-grid decodes
- **Adaptive threshold** for `decode_ssle.py` — auto-tune per image instead of fixed `--threshold`
- **Better fiducial detection** — current contour-based approach fails in poor lighting; SIFT/ORB matching would be more robust
- **50µm pitch validation** — does the xTool F2 Ultra reliably resolve dots at 50µm spacing in JGS2 glass?
- **Z-layer capture automation** in `scan_disc.py` for `decode_ssle_3d.py` input

### Documentation
- **Real engrave + read log** — if you have an xTool F2 Ultra, document your settings and share the results in an Issue
- **Build log / photos** — assembling the Pi + stage rig
- **Video walkthrough** of the full pipeline

### Encoding
- **Reed-Solomon tuning** — what ECC level is optimal for real glass scans? (baseline: ECC=20)
- **Fountain codes** (Raptor/LT) as an alternative to RS for highly noisy scans

---

## How to Open a Good PR

```
Title: [short description of what changed]
Body:
- What: [one sentence]
- Why: [how this helps the mission]
- Tested on: [hardware used, or "simulation only"]
```

Issues and discussions are open. Let's build this together.
