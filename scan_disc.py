#!/usr/bin/env python3
"""
scan_disc.py — Automated full-disc raster scan.
Uses stage_control.py + picamera2 to scan across an engraved glass disc,
capturing one image per position. Images are saved with coordinates for
stitching or tile-by-tile decode.

Usage:
    python3 scan_disc.py                          # 20x20mm scan, 0.5mm steps
    python3 scan_disc.py --width 10 --step 0.3   # smaller scan, finer steps
    python3 scan_disc.py --sim                    # simulation mode (no hardware)

Output:
    raw_scattering/scan_<x>_<y>.png  — one image per position
    raw_scattering/scan_manifest.txt — list of captured positions

After scanning, run decode_ssle.py on the specific tile containing your data,
or use the full stitch + decode workflow (coming in v0.3).
"""

import argparse
import os
import time

try:
    from picamera2 import Picamera2
    _CAM_AVAILABLE = True
except ImportError:
    _CAM_AVAILABLE = False

from stage_control import Stage

OUTPUT_DIR = 'raw_scattering'
MANIFEST   = os.path.join(OUTPUT_DIR, 'scan_manifest.txt')


def init_camera(simulate=False):
    if simulate or not _CAM_AVAILABLE:
        print("[camera] Simulation mode — no camera output")
        return None
    cam = Picamera2()
    config = cam.create_still_configuration(main={"size": (4056, 3040)})
    cam.configure(config)
    cam.start()
    time.sleep(0.5)  # let sensor settle
    return cam


def capture(cam, path, simulate=False):
    if simulate or cam is None:
        print(f"[camera] SIM capture → {path}")
        return
    import cv2
    img = cam.capture_array()
    cv2.imwrite(path, img)


def scan(width_mm, height_mm, step_mm, start_x, start_y, simulate):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    stage = Stage(simulate=simulate)
    cam   = init_camera(simulate)

    try:
        if not simulate:
            ans = input("[scan] Home stage before scanning? [y/N] ").strip().lower()
            if ans == 'y':
                stage.home()

        positions = list(stage.raster_scan(width_mm, height_mm, step_mm, start_x, start_y))
        total = len(positions)
        print(f"[scan] {total} positions  |  step={step_mm}mm  |  area={width_mm}×{height_mm}mm")
        print(f"[scan] Estimated time: ~{total * 2}s at 2s/position")

        if not simulate:
            input("[scan] Press Enter to start scan (Ctrl+C to abort)...")

        with open(MANIFEST, 'w') as mf:
            mf.write("x_mm,y_mm,file\n")
            for n, (x, y) in enumerate(positions):
                stage.move_to(x, y)
                time.sleep(0.1)  # brief settle

                fname = f"scan_{x:.2f}_{y:.2f}.png".replace('-', 'n')
                fpath = os.path.join(OUTPUT_DIR, fname)
                capture(cam, fpath, simulate)
                mf.write(f"{x:.3f},{y:.3f},{fname}\n")

                print(f"[scan] {n+1}/{total}  ({x:.2f}, {y:.2f}) → {fname}")

        print(f"\n[scan] Done. {total} images saved to {OUTPUT_DIR}/")
        print(f"[scan] Manifest: {MANIFEST}")
        print()
        print("Next steps:")
        print(f"  Single tile decode : python3 decode_ssle.py {OUTPUT_DIR}/scan_0.00_0.00.png")
        print(f"  (Full stitch + decode coming in v0.3)")

    finally:
        if cam is not None:
            cam.stop()
        stage.move_to(0, 0)
        stage.cleanup()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Automated raster disc scan')
    parser.add_argument('--width',   type=float, default=20.0,
                        help='Scan width in mm (default: 20)')
    parser.add_argument('--height',  type=float, default=20.0,
                        help='Scan height in mm (default: 20)')
    parser.add_argument('--step',    type=float, default=0.5,
                        help='Step size in mm (default: 0.5 — matches typical camera FOV)')
    parser.add_argument('--start-x', type=float, default=0.0,
                        help='Start X position in mm (default: 0)')
    parser.add_argument('--start-y', type=float, default=0.0,
                        help='Start Y position in mm (default: 0)')
    parser.add_argument('--sim',     action='store_true',
                        help='Simulation mode — no GPIO or camera')
    args = parser.parse_args()

    scan(args.width, args.height, args.step, args.start_x, args.start_y, args.sim)
