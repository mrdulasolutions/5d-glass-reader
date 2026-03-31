#!/usr/bin/env python3
"""
encode_ssle.py — Encode any file to an xTool-compatible dot-grid PNG
for subsurface laser engraving into fused silica.

Reed-Solomon error correction is applied automatically (--ecc symbols, default 20).
This allows decode_ssle.py to recover from up to ECC/2 byte errors per 255-byte block
— essential for real glass where engraving or scanning is imperfect.

Usage:
    python3 encode_ssle.py myfile.txt
    python3 encode_ssle.py myfile.txt --output grid.png --cols 200 --rows 200
    python3 encode_ssle.py myfile.txt --cols 400 --rows 400   # more capacity
    python3 encode_ssle.py myfile.txt --ecc 40               # stronger correction

Grid capacity (approximate, default 200x200, ECC=20):
    ~3.9 KB per disc  (ECC overhead ~8.5%)
    ~15 KB at 400x400
"""

import argparse
import math
import os
import struct
import sys
import zlib

import cv2
import numpy as np
from reedsolo import RSCodec

MAGIC = b'5DG\x02'         # v2 = Reed-Solomon enabled
FIDUCIAL_SIZE = 3
BORDER = 1
MAX_FILENAME_LEN = 32
# Header layout: MAGIC(4) + fname_len(1) + fname(32) + file_size(4) + crc32(4) = 45 bytes
HEADER_BYTES = len(MAGIC) + 1 + MAX_FILENAME_LEN + 4 + 4
DEFAULT_ECC = 20            # ECC symbols per 255-byte RS block (corrects up to 10 byte errors)


def file_to_bits(data: bytes) -> list:
    bits = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits


def build_header(filename: str, file_size: int, crc32: int) -> bytes:
    fname_bytes = os.path.basename(filename).encode()[:MAX_FILENAME_LEN]
    fname_padded = fname_bytes.ljust(MAX_FILENAME_LEN, b'\x00')
    return (
        MAGIC
        + bytes([len(fname_bytes)])
        + fname_padded
        + struct.pack('>I', file_size)
        + struct.pack('>I', crc32)
    )


def data_area(grid_cols, grid_rows):
    cols = grid_cols - 2 * (FIDUCIAL_SIZE + BORDER)
    rows = grid_rows - 2 * (FIDUCIAL_SIZE + BORDER)
    return cols, rows


def encode(input_path, grid_cols, grid_rows, dot_size, dot_spacing, output_path, ecc):
    with open(input_path, 'rb') as f:
        file_data = f.read()

    file_size = len(file_data)
    crc32 = zlib.crc32(file_data) & 0xFFFFFFFF
    header = build_header(input_path, file_size, crc32)
    raw_payload = header + file_data

    # Reed-Solomon encode
    rs = RSCodec(ecc)
    rs_payload = bytes(rs.encode(raw_payload))

    payload_bits = file_to_bits(rs_payload)
    dcols, drows = data_area(grid_cols, grid_rows)
    capacity_bits = dcols * drows

    if len(payload_bits) > capacity_bits:
        overhead = len(rs_payload) / len(raw_payload)
        needed = math.ceil(math.sqrt(len(payload_bits) * 1.15))
        print(f"ERROR: File too large for this grid (including RS overhead).")
        print(f"  Capacity   : {capacity_bits} bits ({capacity_bits // 8} bytes)")
        print(f"  RS payload : {len(rs_payload)} bytes (raw {len(raw_payload)}B × {overhead:.2f} RS overhead)")
        print(f"  Fix        : --cols {needed} --rows {needed}")
        sys.exit(1)

    payload_bits += [0] * (capacity_bits - len(payload_bits))

    # Build logical grid
    grid = np.zeros((grid_rows, grid_cols), dtype=np.uint8)

    for ry, rx in [
        (0, 0),
        (0, grid_cols - FIDUCIAL_SIZE),
        (grid_rows - FIDUCIAL_SIZE, 0),
        (grid_rows - FIDUCIAL_SIZE, grid_cols - FIDUCIAL_SIZE),
    ]:
        grid[ry:ry + FIDUCIAL_SIZE, rx:rx + FIDUCIAL_SIZE] = 1

    origin_row = FIDUCIAL_SIZE + BORDER
    origin_col = FIDUCIAL_SIZE + BORDER
    bit_idx = 0
    for row in range(origin_row, origin_row + drows):
        for col in range(origin_col, origin_col + dcols):
            grid[row, col] = payload_bits[bit_idx]
            bit_idx += 1

    # Render PNG: black dots on white background
    cell = dot_spacing
    img_h = grid_rows * cell
    img_w = grid_cols * cell
    img = np.full((img_h, img_w), 255, dtype=np.uint8)
    radius = max(1, dot_size // 2)

    for row in range(grid_rows):
        for col in range(grid_cols):
            if grid[row, col]:
                cx = col * cell + cell // 2
                cy = row * cell + cell // 2
                cv2.circle(img, (cx, cy), radius, 0, -1)

    cv2.imwrite(output_path, img)

    fill = len(payload_bits) / capacity_bits * 100
    grid_mm = (img_w / 300) * 25.4

    print(f"✅  Encoded  : {input_path}")
    print(f"    File     : {file_size} bytes  |  CRC32: {crc32:08X}")
    print(f"    RS ECC   : {ecc} symbols/block  →  corrects up to {ecc//2} byte errors per 255B block")
    print(f"    RS size  : {len(raw_payload)}B raw → {len(rs_payload)}B with ECC")
    print(f"    Grid     : {grid_cols}×{grid_rows}  |  Data area: {dcols}×{drows}  |  {fill:.1f}% full")
    print(f"    PNG      : {output_path}  ({img_w}×{img_h} px)")
    print()
    print(f"📐  xTool F2 Ultra settings:")
    print(f"    Import   : {output_path}")
    print(f"    Size     : {grid_mm:.0f}×{grid_mm:.0f} mm  (set in xTool software)")
    print(f"    Mode     : Subsurface (internal) engraving")
    print(f"    Power    : start 80%  |  Speed: 300 mm/s  (tune for your glass)")
    print(f"    Depth    : ~1 mm below surface for v0.1")
    print()
    print(f"    Decode with: python3 decode_ssle.py --cols {grid_cols} --rows {grid_rows} --ecc {ecc}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Encode a file to an xTool-ready dot-grid PNG (with Reed-Solomon ECC)'
    )
    parser.add_argument('input_file', help='File to encode into glass')
    parser.add_argument('--output', '-o', help='Output PNG path (default: <input>_grid.png)')
    parser.add_argument('--cols', type=int, default=200, help='Grid columns (default: 200)')
    parser.add_argument('--rows', type=int, default=200, help='Grid rows (default: 200)')
    parser.add_argument('--dot-size', type=int, default=6,
                        help='Dot diameter in pixels (default: 6)')
    parser.add_argument('--dot-spacing', type=int, default=10,
                        help='Dot center spacing in pixels (default: 10)')
    parser.add_argument('--ecc', type=int, default=DEFAULT_ECC,
                        help=f'Reed-Solomon ECC symbols per block (default: {DEFAULT_ECC}, corrects up to ECC/2 byte errors)')
    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"ERROR: File not found: {args.input_file}")
        sys.exit(1)

    out = args.output or os.path.splitext(args.input_file)[0] + '_grid.png'
    encode(args.input_file, args.cols, args.rows, args.dot_size, args.dot_spacing, out, args.ecc)
