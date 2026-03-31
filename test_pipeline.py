#!/usr/bin/env python3
"""
test_pipeline.py — Software pipeline verification (no hardware needed).

Runs two complete encode → decode round-trips entirely in software:

  Test 1 — 2D round-trip (encode_ssle → PNG → decode_ssle)
  Test 2 — 3D round-trip (encode_ssle_3d --render-layers → per-layer PNGs → decode_ssle_3d)

Tests:
  1. Encode a generated test file to a dot-grid PNG (2D) or layer PNGs (3D).
  2. Reload the image(s) and decode back using the same logic as the decoders.
  3. Verify filename, file size, and CRC32 match exactly.
  4. Simulate dot-read noise (random bit flips) to test Reed-Solomon recovery.

Usage:
    python3 test_pipeline.py                    # both tests, default 200×200 grid, ECC=20
    python3 test_pipeline.py --cols 400 --rows 400
    python3 test_pipeline.py --noise 50         # flip 50 random dots (RS recovery test)
    python3 test_pipeline.py --file myfile.txt  # test with your own file
    python3 test_pipeline.py --test 2d          # 2D only
    python3 test_pipeline.py --test 3d          # 3D only
"""

import argparse
import hashlib
import os
import random
import sys
import tempfile
import zlib

import cv2
import numpy as np
from reedsolo import RSCodec, ReedSolomonError

sys.path.insert(0, os.path.dirname(__file__))
from encode_ssle import encode as encode_2d, data_area, HEADER_BYTES as HEADER_BYTES_2D
from encode_ssle_3d import encode as encode_3d
from decode_ssle import decode as decode_2d
from decode_ssle_3d import decode as decode_3d
from constants import DEFAULT_ECC, FIDUCIAL_SIZE, BORDER

PASS = "PASS"
FAIL = "FAIL"


def generate_test_file(path, size_bytes=512):
    content = f"5D-GLASS-TEST v0.3 | {size_bytes}B | mrdulasolutions/EternalDrive-IndieHack\n"
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    while len(content) < size_bytes:
        content += alphabet
    content = content[:size_bytes]
    with open(path, 'w') as f:
        f.write(content)
    return content.encode()


def inject_noise(png_path, n_flips, grid_cols, grid_rows):
    """Flip n_flips random dot positions in the PNG to simulate scan noise."""
    img = cv2.imread(png_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0

    dcols = grid_cols - 2 * (FIDUCIAL_SIZE + BORDER)
    drows = grid_rows - 2 * (FIDUCIAL_SIZE + BORDER)
    origin_row = FIDUCIAL_SIZE + BORDER
    origin_col = FIDUCIAL_SIZE + BORDER
    cell_w = img.shape[1] / grid_cols
    cell_h = img.shape[0] / grid_rows

    positions = random.sample(
        [(r, c) for r in range(origin_row, origin_row + drows)
                for c in range(origin_col, origin_col + dcols)],
        min(n_flips, dcols * drows)
    )
    flipped = 0
    for (row, col) in positions:
        cx = int((col + 0.5) * cell_w)
        cy = int((row + 0.5) * cell_h)
        r = max(3, int(min(cell_w, cell_h) * 0.3))
        region = img[max(0, cy - r):cy + r + 1, max(0, cx - r):cx + r + 1]
        if region.mean() > 200:
            cv2.circle(img, (cx, cy), r, 0, -1)
        else:
            cv2.circle(img, (cx, cy), r, 255, -1)
        flipped += 1

    cv2.imwrite(png_path, img)
    return flipped


def _print_results(results):
    print(f"\n{'─'*52}")
    print(f"  {'Test':<30} {'Result':<8} Notes")
    print(f"{'─'*52}")
    for name, result, note in results:
        status = "OK" if result == PASS else "!!"
        print(f"  [{status}] {name:<30} {note}")
    print(f"{'─'*52}")


def run_2d_test(cols, rows, ecc, noise, input_file):
    print(f"\n{'='*60}")
    print(f"Test 1 — 2D Pipeline  |  Grid: {cols}×{rows}  ECC: {ecc}  Noise: {noise}")
    print(f"{'='*60}\n")

    results = []

    with tempfile.TemporaryDirectory() as tmpdir:
        # Prepare test file
        if input_file:
            src_path = input_file
            with open(src_path, 'rb') as f:
                src_bytes = f.read()
            print(f"[1] Source file   : {src_path}  ({len(src_bytes)} bytes)")
        else:
            src_path = os.path.join(tmpdir, 'test_input.txt')
            dcols, drows = data_area(cols, rows)
            capacity = (dcols * drows) // 8
            rs_overhead = 1 + ecc / (255 - ecc)
            max_raw = int(capacity / rs_overhead) - HEADER_BYTES_2D
            target = max(64, int(max_raw * 0.6))
            src_bytes = generate_test_file(src_path, target)
            print(f"[1] Generated file : {src_path}  ({len(src_bytes)} bytes)")

        src_hash = hashlib.sha256(src_bytes).hexdigest()[:16]
        src_crc  = zlib.crc32(src_bytes) & 0xFFFFFFFF
        print(f"    SHA-256[:16]: {src_hash}  CRC32: {src_crc:08X}")

        # Encode
        grid_path = os.path.join(tmpdir, 'grid.png')
        print(f"\n[2] Encoding → {grid_path}")
        try:
            encode_2d(src_path, cols, rows, dot_size=6, dot_spacing=10,
                      output_path=grid_path, ecc=ecc, levels=4)
            results.append(("2D Encode", PASS, ""))
        except SystemExit as e:
            results.append(("2D Encode", FAIL, str(e)))
            _print_results(results)
            return False

        # Inject noise
        if noise > 0:
            print(f"\n[3] Injecting {noise} random dot flips...")
            actual = inject_noise(grid_path, noise, cols, rows)
            print(f"    Flipped {actual} dots")
            results.append(("Noise injection", PASS, f"{actual} dots flipped"))
        else:
            print(f"\n[3] Clean round-trip (no noise)")

        # Decode
        out_dir = os.path.join(tmpdir, 'output')
        print(f"\n[4] Decoding → {out_dir}/")
        try:
            decode_2d(grid_path, out_dir, cols, rows, threshold=80, ecc=ecc, levels=4)
        except SystemExit as e:
            results.append(("2D Decode", FAIL, f"RS or alignment failure: {e}"))
            _print_results(results)
            return False

        # Verify
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

        results.append(("2D File size match",  PASS if size_ok  else FAIL, f"{len(out_bytes)}B"))
        results.append(("2D CRC32 match",      PASS if crc_ok   else FAIL, ""))
        results.append(("2D SHA-256 match",    PASS if hash_ok  else FAIL, ""))

        all_passed = all(r[1] == PASS for r in results)

    _print_results(results)
    return all_passed


def run_3d_test(cols, rows, ecc, noise, input_file):
    print(f"\n{'='*60}")
    print(f"Test 2 — 3D Pipeline  |  Grid: {cols}×{rows}×3 layers  ECC: {ecc}  Noise: {noise}")
    print(f"{'='*60}\n")

    results = []
    layers = 3  # small for speed; still exercises all the 3D code paths

    with tempfile.TemporaryDirectory() as tmpdir:
        # Prepare test file — size to ~50% of 3D grid capacity
        if input_file:
            src_path = input_file
            with open(src_path, 'rb') as f:
                src_bytes = f.read()
            print(f"[1] Source file   : {src_path}  ({len(src_bytes)} bytes)")
        else:
            src_path = os.path.join(tmpdir, 'test_input_3d.txt')
            from constants import HEADER_BYTES, FIDUCIAL_SIZE, BORDER
            dc = cols - 2 * (FIDUCIAL_SIZE + BORDER)
            dr = rows - 2 * (FIDUCIAL_SIZE + BORDER)
            capacity = (dc * dr * layers * 2) // 8   # 4-level = 2 bpp
            rs_overhead = 1 + ecc / (255 - ecc)
            max_raw = int(capacity / rs_overhead) - HEADER_BYTES
            target = max(64, int(max_raw * 0.5))
            src_bytes = generate_test_file(src_path, target)
            print(f"[1] Generated file : {src_path}  ({len(src_bytes)} bytes)")

        src_hash = hashlib.sha256(src_bytes).hexdigest()[:16]
        src_crc  = zlib.crc32(src_bytes) & 0xFFFFFFFF
        print(f"    SHA-256[:16]: {src_hash}  CRC32: {src_crc:08X}")

        # Encode with --render-layers
        stl_base = os.path.join(tmpdir, 'test_voxel.stl')
        print(f"\n[2] Encoding → STLs + layer PNGs")
        try:
            layer_pngs = encode_3d(
                src_path, cols, rows, layers,
                xy_pitch=0.10, z_pitch=0.50,
                output_path=stl_base, ecc=ecc, levels=4,
                render_layers=True
            )
            results.append(("3D Encode + render-layers", PASS, f"{len(layer_pngs)} PNGs"))
        except SystemExit as e:
            results.append(("3D Encode", FAIL, str(e)))
            _print_results(results)
            return False

        if not layer_pngs:
            results.append(("Layer PNGs generated", FAIL, "no PNGs returned"))
            _print_results(results)
            return False

        layers_dir = os.path.dirname(layer_pngs[0])

        # Inject noise into first layer PNG (tests per-layer RS recovery)
        if noise > 0:
            print(f"\n[3] Injecting {noise} random dot flips into layer_00.png...")
            actual = inject_noise(layer_pngs[0], noise, cols, rows)
            print(f"    Flipped {actual} dots")
            results.append(("3D Noise injection", PASS, f"{actual} dots in layer_00"))
        else:
            print(f"\n[3] Clean round-trip (no noise)")

        # Decode from layer PNGs
        out_dir = os.path.join(tmpdir, 'output_3d')
        print(f"\n[4] Decoding from {layers_dir}/ → {out_dir}/")
        try:
            decode_3d(layers_dir, out_dir, cols, rows,
                      n_layers=layers, threshold=80, ecc=ecc, levels=4)
        except SystemExit as e:
            results.append(("3D Decode", FAIL, f"RS or alignment failure: {e}"))
            _print_results(results)
            return False

        # Verify
        print(f"\n[5] Verifying output...")
        out_name = os.path.basename(src_path)
        out_path = os.path.join(out_dir, out_name)

        if not os.path.exists(out_path):
            results.append(("3D Output file exists", FAIL, f"not found: {out_path}"))
            _print_results(results)
            return False

        with open(out_path, 'rb') as f:
            out_bytes = f.read()

        size_ok = len(out_bytes) == len(src_bytes)
        crc_ok  = zlib.crc32(out_bytes) & 0xFFFFFFFF == src_crc
        hash_ok = hashlib.sha256(out_bytes).hexdigest()[:16] == src_hash

        results.append(("3D File size match",  PASS if size_ok  else FAIL, f"{len(out_bytes)}B"))
        results.append(("3D CRC32 match",      PASS if crc_ok   else FAIL, ""))
        results.append(("3D SHA-256 match",    PASS if hash_ok  else FAIL, ""))

        all_passed = all(r[1] == PASS for r in results)

    _print_results(results)
    return all_passed


def print_density_table():
    print("\nxTool F2 Ultra — Inner Engraving Density Reference (70x70 mm area)")
    print(f"{'Pitch (um)':<14} {'Grid':<14} {'Raw dots':<14} {'Raw KB':<10} {'After ECC=20'}")
    print("-" * 70)
    for pitch_um in [50, 75, 100, 150, 200]:
        pitch_mm = pitch_um / 1000
        cols = int(70 / pitch_mm)
        rows = int(70 / pitch_mm)
        dots = cols * rows
        raw_kb = dots / 8 / 1024
        ecc_kb = raw_kb * (1 - 0.085)
        print(f"  {pitch_um:<12} {cols}x{rows:<10} {dots:<14,} {raw_kb:<10.1f} {ecc_kb:.1f} KB")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Verify the full encode->decode pipeline without hardware'
    )
    parser.add_argument('--cols',   type=int, default=200,   help='Grid columns (default: 200)')
    parser.add_argument('--rows',   type=int, default=200,   help='Grid rows (default: 200)')
    parser.add_argument('--ecc',    type=int, default=DEFAULT_ECC,
                        help=f'Reed-Solomon ECC symbols (default: {DEFAULT_ECC})')
    parser.add_argument('--noise',  type=int, default=0,
                        help='Random dot flips to inject (tests RS recovery, default: 0)')
    parser.add_argument('--file',   help='Test with a specific file instead of generated data')
    parser.add_argument('--test',   choices=['2d', '3d', 'both'], default='both',
                        help='Which pipeline to test (default: both)')
    parser.add_argument('--density', action='store_true',
                        help='Print density reference table and exit')
    args = parser.parse_args()

    if args.density:
        print_density_table()
        sys.exit(0)

    passed_2d = True
    passed_3d = True

    if args.test in ('2d', 'both'):
        passed_2d = run_2d_test(args.cols, args.rows, args.ecc, args.noise, args.file)

    if args.test in ('3d', 'both'):
        passed_3d = run_3d_test(args.cols, args.rows, args.ecc, args.noise, args.file)

    all_ok = passed_2d and passed_3d
    print()
    if all_ok:
        print("ALL TESTS PASSED — pipeline is ready for hardware!")
    else:
        print("TESTS FAILED — check errors above before engraving.")

    sys.exit(0 if all_ok else 1)
