#!/usr/bin/env python3
"""
test_pipeline.py — Software pipeline verification (no hardware needed).

Runs the complete encode → PNG → decode round-trip entirely in software,
so you can confirm the pipeline is working before you ever touch the xTool.

Tests:
  1. Encode a generated test file to a dot-grid PNG.
  2. Reload the PNG and decode it back using the same logic as decode_ssle.py.
  3. Verify filename, file size, and CRC32 match exactly.
  4. Simulate dot-read noise (random bit flips) to test Reed-Solomon recovery.

Usage:
    python3 test_pipeline.py                    # default 200x200 grid, ECC=20
    python3 test_pipeline.py --cols 400 --rows 400
    python3 test_pipeline.py --noise 50         # flip 50 random dots (RS recovery test)
    python3 test_pipeline.py --file myfile.txt  # test with your own file
"""

import argparse
import hashlib
import math
import os
import random
import struct
import sys
import tempfile
import zlib

import cv2
import numpy as np
from reedsolo import RSCodec, ReedSolomonError

# Import shared constants + logic from encode/decode
sys.path.insert(0, os.path.dirname(__file__))
from encode_ssle import encode, data_area, HEADER_BYTES, DEFAULT_ECC as ENC_DEFAULT_ECC
from decode_ssle import decode, DEFAULT_ECC as DEC_DEFAULT_ECC

PASS = "✅ PASS"
FAIL = "❌ FAIL"


def generate_test_file(path, size_bytes=512):
    """
    Write a deterministic test file: a header line + repeating ASCII pattern.
    Small enough for default 200x200 grid, human-readable if you open it.
    """
    content = f"5D-GLASS-TEST v0.2 | {size_bytes}B | mrdulasolutions/5d-glass-reader\n"
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    while len(content) < size_bytes:
        content += alphabet
    content = content[:size_bytes]
    with open(path, 'w') as f:
        f.write(content)
    return content.encode()


def inject_noise(png_path, n_flips, grid_cols, grid_rows):
    """
    Flip n_flips random dot positions in the PNG to simulate scan noise.
    Returns number of bits actually flipped.
    """
    from encode_ssle import FIDUCIAL_SIZE, BORDER
    img = cv2.imread(png_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0

    dcols = grid_cols - 2 * (FIDUCIAL_SIZE + BORDER)
    drows = grid_rows - 2 * (FIDUCIAL_SIZE + BORDER)
    origin_row = FIDUCIAL_SIZE + BORDER
    origin_col = FIDUCIAL_SIZE + BORDER
    cell_w = img.shape[1] / grid_cols
    cell_h = img.shape[0] / grid_rows

    flipped = 0
    positions = random.sample(
        [(r, c) for r in range(origin_row, origin_row + drows)
                for c in range(origin_col, origin_col + dcols)],
        min(n_flips, dcols * drows)
    )
    for (row, col) in positions:
        cx = int((col + 0.5) * cell_w)
        cy = int((row + 0.5) * cell_h)
        r = max(3, int(min(cell_w, cell_h) * 0.3))
        # Toggle: white region → black dot (or vice versa)
        region = img[max(0, cy-r):cy+r+1, max(0, cx-r):cx+r+1]
        if region.mean() > 200:
            cv2.circle(img, (cx, cy), r, 0, -1)
        else:
            cv2.circle(img, (cx, cy), r, 255, -1)
        flipped += 1

    cv2.imwrite(png_path, img)
    return flipped


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        h.update(f.read())
    return h.hexdigest()


def run_test(cols, rows, ecc, noise, input_file):
    print(f"\n{'='*60}")
    print(f"5D Glass Reader — Pipeline Test")
    print(f"Grid: {cols}×{rows}  |  ECC: {ecc}  |  Noise: {noise} flips")
    print(f"{'='*60}\n")

    results = []

    with tempfile.TemporaryDirectory() as tmpdir:
        # ── Step 1: Prepare test file ──────────────────────────────
        if input_file:
            src_path = input_file
            with open(src_path, 'rb') as f:
                src_bytes = f.read()
            print(f"[1] Source file   : {src_path}  ({len(src_bytes)} bytes)")
        else:
            src_path = os.path.join(tmpdir, 'test_input.txt')
            # Size the test file to ~60% of grid capacity
            from encode_ssle import FIDUCIAL_SIZE, BORDER
            dcols, drows = data_area(cols, rows)
            capacity = (dcols * drows) // 8
            rs_overhead = 1 + ecc / (255 - ecc)
            max_raw = int(capacity / rs_overhead) - HEADER_BYTES
            target = max(64, int(max_raw * 0.6))
            src_bytes = generate_test_file(src_path, target)
            print(f"[1] Generated file : {src_path}  ({len(src_bytes)} bytes)")

        src_hash = hashlib.sha256(src_bytes).hexdigest()[:16]
        src_crc  = zlib.crc32(src_bytes) & 0xFFFFFFFF
        print(f"    SHA-256 (first 16): {src_hash}")
        print(f"    CRC32             : {src_crc:08X}")

        # ── Step 2: Encode ────────────────────────────────────────
        grid_path = os.path.join(tmpdir, 'grid.png')
        print(f"\n[2] Encoding → {grid_path}")
        try:
            encode(src_path, cols, rows, dot_size=6, dot_spacing=10,
                   output_path=grid_path, ecc=ecc)
            results.append(("Encode", PASS, ""))
        except SystemExit as e:
            results.append(("Encode", FAIL, str(e)))
            _print_results(results)
            return False

        # ── Step 3: Inject noise ──────────────────────────────────
        if noise > 0:
            print(f"\n[3] Injecting {noise} random dot flips (RS recovery test)...")
            actual = inject_noise(grid_path, noise, cols, rows)
            print(f"    Flipped {actual} dots")
            results.append(("Noise injection", PASS, f"{actual} dots flipped"))
        else:
            print(f"\n[3] No noise injection (clean round-trip test)")

        # ── Step 4: Decode ────────────────────────────────────────
        out_dir = os.path.join(tmpdir, 'output')
        print(f"\n[4] Decoding → {out_dir}/")
        try:
            decode(grid_path, out_dir, cols, rows, threshold=80, ecc=ecc)
        except SystemExit as e:
            results.append(("Decode", FAIL, f"RS or alignment failure: {e}"))
            _print_results(results)
            return False

        # ── Step 5: Verify ────────────────────────────────────────
        print(f"\n[5] Verifying output...")
        out_name = os.path.basename(src_path)
        out_path = os.path.join(out_dir, out_name)

        if not os.path.exists(out_path):
            results.append(("Output file exists", FAIL, f"not found: {out_path}"))
            _print_results(results)
            return False

        with open(out_path, 'rb') as f:
            out_bytes = f.read()

        size_ok = len(out_bytes) == len(src_bytes)
        crc_ok  = zlib.crc32(out_bytes) & 0xFFFFFFFF == src_crc
        hash_ok = hashlib.sha256(out_bytes).hexdigest()[:16] == src_hash

        results.append(("File size match",  PASS if size_ok  else FAIL,
                         f"{len(out_bytes)}B vs {len(src_bytes)}B"))
        results.append(("CRC32 match",      PASS if crc_ok   else FAIL, ""))
        results.append(("SHA-256 match",    PASS if hash_ok  else FAIL, ""))

        all_passed = all(r[1] == PASS for r in results)

    _print_results(results)

    print()
    if all_passed:
        print("🎉 ALL TESTS PASSED — pipeline is ready for hardware!")
        if noise > 0:
            rs = RSCodec(ecc)
            block_size = 255 - ecc
            max_correctable_per_block = ecc // 2
            print(f"   RS recovered up to {noise} flipped dots across the grid.")
            print(f"   Each {255}-byte RS block tolerates {max_correctable_per_block} byte errors.")
    else:
        print("💥 TESTS FAILED — check errors above before engraving.")

    return all_passed


def _print_results(results):
    print(f"\n{'─'*50}")
    print(f"{'Test':<30} {'Result':<10} Notes")
    print(f"{'─'*50}")
    for name, result, note in results:
        print(f"  {name:<28} {result:<10} {note}")
    print(f"{'─'*50}")


# ── Density calculator (bonus utility) ───────────────────────────────────────

def print_density_table():
    """Print the xTool F2 Ultra inner-area density reference table."""
    print("\n📐 xTool F2 Ultra — Inner Engraving Density Reference (70×70 mm area)")
    print(f"{'Pitch (µm)':<14} {'Grid':<14} {'Raw dots':<14} {'Raw KB':<10} {'After ECC=20 (~8.5%)'}")
    print("─" * 70)
    for pitch_um in [50, 75, 100, 150, 200]:
        pitch_mm = pitch_um / 1000
        cols = int(70 / pitch_mm)
        rows = int(70 / pitch_mm)
        dots = cols * rows
        raw_kb = dots / 8 / 1024
        ecc_kb = raw_kb * (1 - 0.085)
        print(f"  {pitch_um:<12} {cols}×{rows:<10} {dots:<14,} {raw_kb:<10.1f} {ecc_kb:.1f} KB")
    print()
    print("  Recommended starting pitch: 100 µm (safe, well above 20 µm spot size)")
    print("  Aggressive pitch:           50 µm  (needs careful power/speed tuning)")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Verify the full encode→decode pipeline without hardware'
    )
    parser.add_argument('--cols',   type=int, default=200,   help='Grid columns (default: 200)')
    parser.add_argument('--rows',   type=int, default=200,   help='Grid rows (default: 200)')
    parser.add_argument('--ecc',    type=int, default=ENC_DEFAULT_ECC,
                        help=f'Reed-Solomon ECC symbols (default: {ENC_DEFAULT_ECC})')
    parser.add_argument('--noise',  type=int, default=0,
                        help='Number of random dot flips to inject (tests RS recovery, default: 0)')
    parser.add_argument('--file',   help='Test with a specific file instead of generated data')
    parser.add_argument('--density', action='store_true',
                        help='Print density reference table for xTool F2 Ultra and exit')
    args = parser.parse_args()

    if args.density:
        print_density_table()
        sys.exit(0)

    ok = run_test(args.cols, args.rows, args.ecc, args.noise, args.file)
    sys.exit(0 if ok else 1)
