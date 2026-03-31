#!/usr/bin/env python3
"""
encode_ssle.py — Encode any file to an xTool-compatible grayscale dot-grid PNG
for subsurface laser engraving into fused silica / K9 crystal.

TRUE 5D STORAGE:
  Dimension 1 — X position of dot
  Dimension 2 — Y position of dot
  Dimension 3 — Z depth (set in xTool Studio inner engraving)
  Dimension 4 — Dot presence (engrave here or not)
  Dimension 5 — Dot SIZE (small / medium / large, controlled by gray level)

With --levels 4 (default), each grid position encodes 2 bits (4 states):
  0 = no dot     (white pixel  → no laser)
  1 = small dot  (gray 192     → low power/duration → small scattering bubble)
  2 = medium dot (gray 128     → medium power       → medium bubble)
  3 = large dot  (gray 0/black → full power         → large bubble)

xTool Studio grayscale mode maps pixel brightness → laser dwell time → dot size.
Load the output PNG in xTool Studio → Grayscale mode → inner engraving.

Capacity vs. binary (--levels 2):
  4-level: 2 bits/position → 2× the data in the same physical grid area

Usage:
    python3 encode_ssle.py myfile.txt                     # true 5D, 4-level
    python3 encode_ssle.py myfile.txt --levels 2          # binary (backward compat)
    python3 encode_ssle.py myfile.txt --cols 400 --rows 400
    python3 encode_ssle.py myfile.txt --ecc 40            # stronger RS correction
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

# ── Format versions ───────────────────────────────────────────────────────────
MAGIC_BINARY  = b'5DG\x02'   # legacy binary (1 bit/position)
MAGIC_5D      = b'5DG\x03'   # true 5D (multi-level, 2 bits/position for 4-level)

FIDUCIAL_SIZE = 3
BORDER        = 1
MAX_FILENAME_LEN = 32
# Header: MAGIC(4) + levels(1) + fname_len(1) + fname(32) + file_size(4) + crc32(4) = 46 bytes
HEADER_BYTES  = 4 + 1 + 1 + MAX_FILENAME_LEN + 4 + 4
DEFAULT_ECC   = 20
DEFAULT_LEVELS = 4

# Gray values for each level: 0=no dot(white), 1=small, 2=medium, 3=large(black)
# Darker pixel → more laser power in xTool grayscale mode → larger scattering bubble
GRAY = {0: 255, 1: 192, 2: 128, 3: 0}


def bits_per_position(levels):
    return int(math.log2(levels))  # levels=4 → 2, levels=2 → 1


def file_to_symbols(data: bytes, levels: int) -> list:
    """Convert bytes to base-`levels` symbols (2 bits each for 4-level)."""
    bpp = bits_per_position(levels)
    bits = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    # Pad to multiple of bpp
    while len(bits) % bpp:
        bits.append(0)
    symbols = []
    for i in range(0, len(bits), bpp):
        val = 0
        for b in bits[i:i+bpp]:
            val = (val << 1) | b
        symbols.append(val)
    return symbols


def symbols_to_bits(symbols: list, levels: int) -> list:
    bpp = bits_per_position(levels)
    bits = []
    for sym in symbols:
        for i in range(bpp-1, -1, -1):
            bits.append((sym >> i) & 1)
    return bits


def build_header(filename: str, file_size: int, crc32: int, levels: int) -> bytes:
    fname = os.path.basename(filename).encode()[:MAX_FILENAME_LEN]
    return (
        MAGIC_5D
        + bytes([levels])
        + bytes([len(fname)])
        + fname.ljust(MAX_FILENAME_LEN, b'\x00')
        + struct.pack('>I', file_size)
        + struct.pack('>I', crc32)
    )


def data_area(grid_cols, grid_rows):
    cols = grid_cols - 2 * (FIDUCIAL_SIZE + BORDER)
    rows = grid_rows - 2 * (FIDUCIAL_SIZE + BORDER)
    return cols, rows


def encode(input_path, grid_cols, grid_rows, dot_size, dot_spacing, output_path, ecc, levels):
    with open(input_path, 'rb') as f:
        file_data = f.read()

    file_size = len(file_data)
    crc32 = zlib.crc32(file_data) & 0xFFFFFFFF
    header = build_header(input_path, file_size, crc32, levels)
    raw_payload = header + file_data

    # Reed-Solomon encode
    rs = RSCodec(ecc)
    rs_payload = bytes(rs.encode(raw_payload))

    # Convert to symbols (2 bits each for 4-level)
    bpp = bits_per_position(levels)
    payload_symbols = file_to_symbols(rs_payload, levels)

    dcols, drows = data_area(grid_cols, grid_rows)
    capacity_symbols = dcols * drows
    capacity_bits    = capacity_symbols * bpp

    if len(payload_symbols) > capacity_symbols:
        needed = math.ceil(math.sqrt(len(payload_symbols) * 1.15))
        print(f"ERROR: File too large for this grid.")
        print(f"  Capacity  : {capacity_symbols} positions × {bpp} bits = {capacity_bits} bits ({capacity_bits//8} bytes)")
        print(f"  Needed    : {len(payload_symbols)} symbols")
        print(f"  Fix       : --cols {needed} --rows {needed}")
        sys.exit(1)

    # Pad
    payload_symbols += [0] * (capacity_symbols - len(payload_symbols))

    # Build grayscale grid (0=no dot, 1=small, 2=medium, 3=large)
    grid = np.zeros((grid_rows, grid_cols), dtype=np.uint8)

    # Fiducial markers at corners (always level 3 = solid black = max dot)
    for ry, rx in [(0,0), (0, grid_cols-FIDUCIAL_SIZE),
                   (grid_rows-FIDUCIAL_SIZE, 0), (grid_rows-FIDUCIAL_SIZE, grid_cols-FIDUCIAL_SIZE)]:
        grid[ry:ry+FIDUCIAL_SIZE, rx:rx+FIDUCIAL_SIZE] = 3

    # Fill data area
    origin_r = FIDUCIAL_SIZE + BORDER
    origin_c = FIDUCIAL_SIZE + BORDER
    sym_idx = 0
    for row in range(origin_r, origin_r + drows):
        for col in range(origin_c, origin_c + dcols):
            grid[row, col] = payload_symbols[sym_idx]
            sym_idx += 1

    # Render grayscale PNG
    cell = dot_spacing
    img_h = grid_rows * cell
    img_w = grid_cols * cell
    img = np.full((img_h, img_w), 255, dtype=np.uint8)  # white background
    radius = max(1, dot_size // 2)

    for row in range(grid_rows):
        for col in range(grid_cols):
            level = grid[row, col]
            if level > 0:
                cx = col * cell + cell // 2
                cy = row * cell + cell // 2
                # Scale radius by level for visual clarity (xTool grayscale handles power)
                r = max(1, int(radius * (0.5 + 0.5 * level / (levels - 1))))
                cv2.circle(img, (cx, cy), r, GRAY[level], -1)

    cv2.imwrite(output_path, img)

    fill = len(payload_symbols) / capacity_symbols * 100
    grid_mm = (img_w / 300) * 25.4
    raw_bits_used = len(file_to_symbols(rs_payload, levels)) * bpp

    print(f"✅  5D Encoded : {input_path}")
    print(f"    File      : {file_size} bytes  |  CRC32: {crc32:08X}")
    print(f"    Levels    : {levels} ({bpp} bits/position) — Dimension 5 = dot size")
    print(f"    RS ECC    : {ecc} symbols/block  →  corrects up to {ecc//2} byte errors/block")
    print(f"    RS size   : {len(raw_payload)}B raw → {len(rs_payload)}B with ECC")
    print(f"    Grid      : {grid_cols}×{grid_rows}  |  Data area: {dcols}×{drows}  |  {fill:.1f}% full")
    print(f"    Capacity  : {capacity_bits//8} bytes usable @ {levels}-level (vs {capacity_bits//8//bpp}B binary)")
    print(f"    PNG       : {output_path}  ({img_w}×{img_h} px)")
    print()
    print(f"📐  xTool F2 Ultra — True 5D Inner Engraving:")
    print(f"    Import    : {output_path}")
    print(f"    Size      : {grid_mm:.0f}×{grid_mm:.0f} mm  (set in xTool Studio)")
    print(f"    Mode      : Grayscale inner engraving (NOT bitmap/dotting)")
    print(f"              : Pixel brightness → laser dwell time → dot size (the 5th dimension)")
    print(f"    Power     : 80% base  |  Speed: 300 mm/s  (tune per glass type)")
    print(f"    Depth     : ~1 mm below surface")
    print()
    print(f"    xTool grayscale level map:")
    print(f"      White (255) = no dot    (level 0)")
    print(f"      Gray  (192) = small dot (level 1, ~60% power)")
    print(f"      Gray  (128) = med dot   (level 2, ~80% power)")
    print(f"      Black (  0) = large dot (level 3, 100% power)")
    print()
    print(f"    Decode with: python3 decode_ssle.py --cols {grid_cols} --rows {grid_rows} --ecc {ecc}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Encode a file to a True 5D grayscale dot-grid PNG for xTool SSLE glass engraving'
    )
    parser.add_argument('input_file', help='File to encode into glass')
    parser.add_argument('--output', '-o', help='Output PNG (default: <input>_5d.png)')
    parser.add_argument('--cols',   type=int, default=200)
    parser.add_argument('--rows',   type=int, default=200)
    parser.add_argument('--dot-size',    type=int, default=6)
    parser.add_argument('--dot-spacing', type=int, default=10)
    parser.add_argument('--ecc',    type=int, default=DEFAULT_ECC,
                        help=f'Reed-Solomon ECC symbols (default: {DEFAULT_ECC})')
    parser.add_argument('--levels', type=int, default=DEFAULT_LEVELS, choices=[2, 4],
                        help='Dot size levels: 4=true 5D (2 bits/pos, 2× capacity), 2=binary (default: 4)')
    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"ERROR: File not found: {args.input_file}")
        sys.exit(1)

    suffix = '_5d.png' if args.levels == 4 else '_grid.png'
    out = args.output or os.path.splitext(args.input_file)[0] + suffix
    encode(args.input_file, args.cols, args.rows, args.dot_size, args.dot_spacing, out, args.ecc, args.levels)
