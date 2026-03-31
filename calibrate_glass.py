#!/usr/bin/env python3
"""
calibrate_glass.py — Per-glass brightness threshold calibration tool.

This script makes the 5D glass reader a real scientific instrument: instead of
guessing at brightness thresholds, you engrave a calibration target, scan it
back, and let this tool measure exactly where your glass puts each level.

The calibration target is a PNG with 4 horizontal zones of known gray levels
(0=white, 1=light gray, 2=mid gray, 3=black/max dot) plus fiducial markers.
Engrave it, scan it, then run --analyze to emit calibration.json.

decode_ssle.py and decode_ssle_3d.py automatically load calibration.json
if it exists in the working directory.

Two modes:

  --generate   Write a calibration target PNG (engrave this, then scan).
               python3 calibrate_glass.py --generate
               python3 calibrate_glass.py --generate --output my_cal.png --cols 200 --rows 200

  --analyze    Load the scanned calibration image and compute thresholds.
               python3 calibrate_glass.py --analyze raw_scattering/cal_scan.png
               Writes calibration.json to the current directory.

Workflow:
  1. python3 calibrate_glass.py --generate --output cal_target.png
  2. Load cal_target.png into xTool Studio → Grayscale inner engraving
     (same settings as your real engraving)
  3. Scan the engraved calibration glass → save image
  4. python3 calibrate_glass.py --analyze <scan_image>
  5. calibration.json is now ready — decoders load it automatically.
"""

import argparse
import json
import os
import sys

import cv2
import numpy as np

from constants import (
    FIDUCIAL_SIZE, BORDER, GRAY, DEFAULT_LEVEL_THRESHOLDS,
    load_calibration,
)

DEFAULT_COLS = 200
DEFAULT_ROWS = 100   # shorter target — 4 zones of 25 rows each
CAL_FILENAME = 'calibration.json'


# ── Generate ──────────────────────────────────────────────────────────────────

def generate(output_path, cols, rows, dot_spacing=10, dot_size=6):
    """
    Write a calibration PNG with 4 horizontal zones, one per gray level.
    Zones are separated by fiducial row markers so the analyzer can find them.

    Zone layout (top to bottom):
      Zone 0 (rows 0..rows/4):       all white (level 0 = no dot)
      Zone 1 (rows rows/4..rows/2):  all light gray (level 1)
      Zone 2 (rows rows/2..3*rows/4): all mid gray  (level 2)
      Zone 3 (rows 3*rows/4..rows):  all black      (level 3)
    """
    zone_rows = rows // 4
    cell = dot_spacing
    img_h = rows * cell
    img_w = cols * cell
    img = np.full((img_h, img_w), 255, dtype=np.uint8)
    radius = max(1, dot_size // 2)

    # Data area bounds (skip fiducial+border on each edge)
    origin_r = FIDUCIAL_SIZE + BORDER
    origin_c = FIDUCIAL_SIZE + BORDER
    dc = cols - 2 * (FIDUCIAL_SIZE + BORDER)
    dr = rows - 2 * (FIDUCIAL_SIZE + BORDER)

    # Fill zones
    for row in range(origin_r, origin_r + dr):
        zone = min(3, (row - origin_r) * 4 // dr)
        for col in range(origin_c, origin_c + dc):
            level = zone
            if level > 0:
                cx = col * cell + cell // 2
                cy = row * cell + cell // 2
                r = max(1, int(radius * (0.5 + 0.5 * level / 3)))
                cv2.circle(img, (cx, cy), r, GRAY[level], -1)

    # Fiducial markers at all 4 corners (level 3 = solid black)
    for ry, rx in [(0, 0), (0, cols - FIDUCIAL_SIZE),
                   (rows - FIDUCIAL_SIZE, 0), (rows - FIDUCIAL_SIZE, cols - FIDUCIAL_SIZE)]:
        for dr2 in range(FIDUCIAL_SIZE):
            for dc2 in range(FIDUCIAL_SIZE):
                cx = (rx + dc2) * cell + cell // 2
                cy = (ry + dr2) * cell + cell // 2
                cv2.circle(img, (cx, cy), max(1, radius), GRAY[3], -1)

    # Zone separator lines (thin horizontal rules)
    for z in range(1, 4):
        row = origin_r + (dr * z) // 4
        y = row * cell
        cv2.line(img, (0, y), (img_w - 1, y), 128, 1)

    cv2.imwrite(output_path, img)
    print(f"Calibration target written: {output_path}")
    print(f"  Grid    : {cols}×{rows}  ({img_w}×{img_h} px)")
    print(f"  Zones   : 4 horizontal bands — white / light gray / mid gray / black")
    print()
    print("Next steps:")
    print(f"  1. Import {output_path} into xTool Studio")
    print(f"  2. Grayscale inner engraving — same settings as your real encode job")
    print(f"  3. Engrave on the same type of glass you use for data")
    print(f"  4. Scan the result (xTool camera / USB scope / Pi HQ)")
    print(f"  5. python3 calibrate_glass.py --analyze <scan_image>")


# ── Analyze ───────────────────────────────────────────────────────────────────

def analyze(scan_path, output_path=CAL_FILENAME, cols=DEFAULT_COLS, rows=DEFAULT_ROWS,
            threshold=80, dot_spacing=10):
    """
    Load a scan of the calibration target, measure per-zone brightness,
    and compute optimal classification thresholds.
    """
    img = cv2.imread(scan_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        print(f"ERROR: Could not load image: {scan_path}")
        sys.exit(1)

    print(f"Loaded scan : {scan_path}  ({img.shape[1]}×{img.shape[0]} px)")

    _, thresh = cv2.threshold(img, threshold, 255, cv2.THRESH_BINARY_INV)

    # Try perspective correction from fiducials
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    candidates = []
    for cnt in contours[:30]:
        if cv2.contourArea(cnt) < 40:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        if 0.4 < w / max(h, 1) < 2.5:
            candidates.append((x + w // 2, y + h // 2))

    if len(candidates) >= 4:
        ih, iw = thresh.shape
        tl = min(candidates, key=lambda p: p[0] ** 2 + p[1] ** 2)
        tr = min(candidates, key=lambda p: (p[0] - iw) ** 2 + p[1] ** 2)
        bl = min(candidates, key=lambda p: p[0] ** 2 + (p[1] - ih) ** 2)
        br = min(candidates, key=lambda p: (p[0] - iw) ** 2 + (p[1] - ih) ** 2)
        if len({tl, tr, bl, br}) == 4:
            side = max(img.shape)
            src = np.float32([tl, tr, bl, br])
            dst = np.float32([[0, 0], [side, 0], [0, side], [side, side]])
            M = cv2.getPerspectiveTransform(src, dst)
            img = cv2.warpPerspective(img, M, (side, side))
            print("Fiducials  : found — perspective correction applied")
        else:
            print("Fiducials  : ambiguous corners — skipping perspective correction")
    else:
        print("Fiducials  : not found — skipping perspective correction")

    # Sample per-zone median dot brightness
    origin_r = FIDUCIAL_SIZE + BORDER
    origin_c = FIDUCIAL_SIZE + BORDER
    dc = cols - 2 * (FIDUCIAL_SIZE + BORDER)
    dr = rows - 2 * (FIDUCIAL_SIZE + BORDER)
    cell_w = img.shape[1] / cols
    cell_h = img.shape[0] / rows

    zone_samples = {0: [], 1: [], 2: [], 3: []}
    for row in range(origin_r, origin_r + dr):
        zone = min(3, (row - origin_r) * 4 // dr)
        for col in range(origin_c, origin_c + dc):
            cx = min(int((col + 0.5) * cell_w), img.shape[1] - 1)
            cy = min(int((row + 0.5) * cell_h), img.shape[0] - 1)
            region = img[max(0, cy - 2):cy + 3, max(0, cx - 2):cx + 3]
            dot_val = float(region.min()) if region.size > 0 else 255.0
            zone_samples[zone].append(dot_val)

    print()
    print("Zone brightness (mean of per-cell minimums):")
    zone_means = {}
    for z in range(4):
        samples = zone_samples[z]
        if samples:
            mean = sum(samples) / len(samples)
            zone_means[z] = mean
            expected_gray = GRAY[z]
            print(f"  Zone {z} (expected gray={expected_gray:3d}) : measured mean = {mean:.1f}  (n={len(samples)})")
        else:
            zone_means[z] = GRAY[z]
            print(f"  Zone {z} : no samples — using default {GRAY[z]}")

    # Compute thresholds as midpoints between adjacent zone means
    t0 = (zone_means[0] + zone_means[1]) / 2   # between level 0 and 1
    t1 = (zone_means[1] + zone_means[2]) / 2   # between level 1 and 2
    t2 = (zone_means[2] + zone_means[3]) / 2   # between level 2 and 3

    thresholds = [round(t0, 1), round(t1, 1), round(t2, 1)]
    defaults   = DEFAULT_LEVEL_THRESHOLDS

    print()
    print("Computed thresholds:")
    print(f"  t0 (0↔1) : {thresholds[0]}  (default: {defaults[0]})")
    print(f"  t1 (1↔2) : {thresholds[1]}  (default: {defaults[1]})")
    print(f"  t2 (2↔3) : {thresholds[2]}  (default: {defaults[2]})")

    # Sanity check — thresholds must be strictly decreasing
    if not (thresholds[0] > thresholds[1] > thresholds[2] > 0):
        print()
        print("WARNING: thresholds are not strictly decreasing — scan may be low quality.")
        print("         Falling back to defaults.")
        thresholds = defaults

    cal = {
        'source_scan': os.path.abspath(scan_path),
        'cols': cols,
        'rows': rows,
        'zone_means': {str(k): round(v, 2) for k, v in zone_means.items()},
        'level_thresholds': thresholds,
        'note': 'Auto-generated by calibrate_glass.py. Used by decode_ssle.py / decode_ssle_3d.py.',
    }

    with open(output_path, 'w') as f:
        json.dump(cal, f, indent=2)

    print()
    print(f"calibration.json written: {output_path}")
    print(f"  Decoders will load this automatically.")
    print(f"  To reset: delete {output_path}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Per-glass brightness threshold calibration for 5D glass reader'
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--generate', action='store_true',
                       help='Generate a calibration target PNG (engrave this, then scan back)')
    group.add_argument('--analyze', metavar='SCAN_IMAGE',
                       help='Analyze a scanned calibration target and write calibration.json')
    parser.add_argument('--output', '-o',
                        help='Output path (PNG for --generate, JSON for --analyze; defaults auto-set)')
    parser.add_argument('--cols',      type=int, default=DEFAULT_COLS)
    parser.add_argument('--rows',      type=int, default=DEFAULT_ROWS)
    parser.add_argument('--threshold', type=int, default=80,
                        help='Fiducial detection threshold (default: 80)')
    args = parser.parse_args()

    if args.generate:
        out = args.output or 'cal_target.png'
        generate(out, args.cols, args.rows)
    else:
        out = args.output or CAL_FILENAME
        analyze(args.analyze, output_path=out, cols=args.cols, rows=args.rows,
                threshold=args.threshold)
