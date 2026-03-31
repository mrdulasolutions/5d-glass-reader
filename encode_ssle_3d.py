#!/usr/bin/env python3
"""
encode_ssle_3d.py — Encode any file to 3D voxel STL(s) for xTool F2 Ultra UV
inner engraving (true volumetric data storage across multiple Z-depth layers).

TRUE 5D+ STORAGE:
  Dimension 1 — X position of voxel
  Dimension 2 — Y position of voxel
  Dimension 3 — Z depth (layer)
  Dimension 4 — Voxel presence (engrave here or not)
  Dimension 5 — Voxel SIZE (small / medium / large) — --levels 4 only

With --levels 4 (default), each grid position encodes 2 bits (4 states):
  0 = no voxel   (omitted from all STLs)
  1 = small voxel  (STL 1: 40% of pitch → lower power pass)
  2 = medium voxel (STL 2: 55% of pitch → medium power pass)
  3 = large voxel  (STL 3: 70% of pitch → full power pass)

Header format (v3, 47 bytes):
  MAGIC(4) + levels(1) + ecc(1) + fname_len(1) + fname(32) + size(4) + crc32(4)

A disc.json sidecar is written after encode so read_disc.sh / decode_ssle_3d.py
can auto-configure without remembering every parameter.

--render-layers  writes a per-layer grayscale PNG alongside the STLs,
                 which enables the software 3D round-trip test in test_pipeline.py
                 and can be used as a visual guide when scanning a disc back.

Usage:
    python3 encode_ssle_3d.py myfile.txt                     # True 5D, 4-level
    python3 encode_ssle_3d.py myfile.txt --levels 2          # binary (1 bit/voxel)
    python3 encode_ssle_3d.py myfile.txt --layers 10
    python3 encode_ssle_3d.py myfile.txt --render-layers     # also emit per-layer PNGs
    python3 encode_ssle_3d.py --capacity --layers 10 --cols 700 --rows 700
"""

import argparse
import json
import math
import os
import struct
import sys
import zlib

import cv2
import numpy as np
from reedsolo import RSCodec

from constants import (
    MAGIC_3D_5D, MAGIC_3D_BINARY,
    FIDUCIAL_SIZE, BORDER, MAX_FILENAME_LEN,
    HEADER_BYTES, DEFAULT_ECC, DEFAULT_LEVELS,
    GRAY, bits_per_position,
)

DEFAULT_COLS       = 200
DEFAULT_ROWS       = 200
DEFAULT_LAYERS     = 5
DEFAULT_XY_PITCH_MM = 0.10   # 100 µm — safe for xTool F2 Ultra (20 µm spot)
DEFAULT_Z_PITCH_MM  = 0.50   # 500 µm between layers

# Voxel size as fraction of pitch, per level (1=small, 2=medium, 3=large)
VOXEL_FRACTION = {1: 0.40, 2: 0.55, 3: 0.70}


# ── STL helpers ──────────────────────────────────────────────────────────────

def _cube_tris(cx, cy, cz, s):
    """12 triangles for a cube at (cx,cy,cz) with side length s."""
    h = s / 2
    v = [
        (cx-h, cy-h, cz-h), (cx+h, cy-h, cz-h),
        (cx+h, cy+h, cz-h), (cx-h, cy+h, cz-h),
        (cx-h, cy-h, cz+h), (cx+h, cy-h, cz+h),
        (cx+h, cy+h, cz+h), (cx-h, cy+h, cz+h),
    ]
    faces_normals = [
        ((v[0], v[2], v[1]), (0,  0, -1)),
        ((v[0], v[3], v[2]), (0,  0, -1)),
        ((v[4], v[5], v[6]), (0,  0,  1)),
        ((v[4], v[6], v[7]), (0,  0,  1)),
        ((v[0], v[1], v[5]), (0, -1,  0)),
        ((v[0], v[5], v[4]), (0, -1,  0)),
        ((v[2], v[3], v[7]), (0,  1,  0)),
        ((v[2], v[7], v[6]), (0,  1,  0)),
        ((v[0], v[4], v[7]), (-1, 0,  0)),
        ((v[0], v[7], v[3]), (-1, 0,  0)),
        ((v[1], v[2], v[6]), (1,  0,  0)),
        ((v[1], v[6], v[5]), (1,  0,  0)),
    ]
    return faces_normals


def write_binary_stl(path, all_tris_normals, label=''):
    n = len(all_tris_normals)
    header = f'5DGlassVoxelSTL mrdulasolutions/5d-glass-reader {label}'.encode()
    with open(path, 'wb') as f:
        f.write(header[:80].ljust(80, b'\x00'))
        f.write(struct.pack('<I', n))
        for (tri, normal) in all_tris_normals:
            f.write(struct.pack('<3f', *normal))
            for vertex in tri:
                f.write(struct.pack('<3f', *vertex))
            f.write(b'\x00\x00')


# ── Encoding helpers ──────────────────────────────────────────────────────────

def file_to_symbols(data: bytes, levels: int) -> list:
    bpp = bits_per_position(levels)
    bits = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    while len(bits) % bpp:
        bits.append(0)
    symbols = []
    for i in range(0, len(bits), bpp):
        val = 0
        for b in bits[i:i + bpp]:
            val = (val << 1) | b
        symbols.append(val)
    return symbols


def data_volume(cols, rows, layers):
    dc = cols - 2 * (FIDUCIAL_SIZE + BORDER)
    dr = rows - 2 * (FIDUCIAL_SIZE + BORDER)
    return dc, dr, layers


def build_header(filename, file_size, crc32, levels, ecc):
    """v3 header: MAGIC(4)+levels(1)+ecc(1)+fname_len(1)+fname(32)+size(4)+crc32(4) = 47 bytes."""
    magic = MAGIC_3D_5D if levels >= 2 else MAGIC_3D_BINARY
    fname = os.path.basename(filename).encode()[:MAX_FILENAME_LEN]
    return (
        magic
        + bytes([levels])
        + bytes([ecc])
        + bytes([len(fname)])
        + fname.ljust(MAX_FILENAME_LEN, b'\x00')
        + struct.pack('>I', file_size)
        + struct.pack('>I', crc32)
    )


def print_capacity(cols, rows, layers, ecc, xy_pitch, z_pitch, levels):
    dc, dr, _ = data_volume(cols, rows, layers)
    bpp = bits_per_position(levels)
    raw_symbols = dc * dr * layers
    raw_bits    = raw_symbols * bpp
    raw_bytes   = raw_bits // 8
    rs_overhead = 1 + ecc / (255 - ecc)
    usable = int(raw_bytes / rs_overhead) - HEADER_BYTES
    vol_x = cols * xy_pitch
    vol_y = rows * xy_pitch
    vol_z = layers * z_pitch
    print(f"\n📦 3D Voxel Grid Capacity  ({levels}-level, {bpp} bits/position)")
    print(f"   Grid      : {cols}×{rows}×{layers} layers")
    print(f"   XY pitch  : {xy_pitch*1000:.0f} µm   Z pitch: {z_pitch*1000:.0f} µm")
    print(f"   Volume    : {vol_x:.1f}×{vol_y:.1f}×{vol_z:.1f} mm")
    print(f"   Raw bits  : {raw_bits:,}  ({raw_bytes/1024:.1f} KB)")
    print(f"   RS ECC={ecc} : {ecc//2} byte errors/block correctable")
    print(f"   Usable    : ~{usable/1024:.1f} KB after header + ECC overhead")
    print(f"   vs binary : {bpp}× the capacity of a binary 3D grid at same density\n")


def render_layer_png(grid_layer, cols, rows, output_path, dot_spacing=10, dot_size=6, levels=4):
    """Render a single-layer 2D PNG from a grid layer (for testing / visual QC)."""
    cell = dot_spacing
    img_h = rows * cell
    img_w = cols * cell
    img = np.full((img_h, img_w), 255, dtype=np.uint8)
    radius = max(1, dot_size // 2)
    for row in range(rows):
        for col in range(cols):
            level = int(grid_layer[row, col])
            if level > 0:
                cx = col * cell + cell // 2
                cy = row * cell + cell // 2
                r = max(1, int(radius * (0.5 + 0.5 * level / (levels - 1))))
                cv2.circle(img, (cx, cy), r, GRAY[level], -1)
    cv2.imwrite(output_path, img)


# ── Main encoder ──────────────────────────────────────────────────────────────

def encode(input_path, cols, rows, layers, xy_pitch, z_pitch, output_path, ecc, levels,
           render_layers=False):
    with open(input_path, 'rb') as f:
        file_data = f.read()

    file_size = len(file_data)
    crc32 = zlib.crc32(file_data) & 0xFFFFFFFF
    header = build_header(input_path, file_size, crc32, levels, ecc)
    raw_payload = header + file_data

    rs = RSCodec(ecc)
    rs_payload = bytes(rs.encode(raw_payload))

    bpp = bits_per_position(levels)
    payload_symbols = file_to_symbols(rs_payload, levels)

    dc, dr, _ = data_volume(cols, rows, layers)
    capacity_symbols = dc * dr * layers

    if len(payload_symbols) > capacity_symbols:
        needed_layers = math.ceil(len(payload_symbols) / (dc * dr))
        print(f"ERROR: File too large for this grid.")
        print(f"  Capacity : {capacity_symbols} positions × {bpp} bits = {capacity_symbols*bpp} bits ({capacity_symbols*bpp//8} bytes)")
        print(f"  Needed   : {len(payload_symbols)} symbols")
        print(f"  Fix      : --layers {needed_layers}  (or increase --cols/--rows)")
        sys.exit(1)

    payload_symbols += [0] * (capacity_symbols - len(payload_symbols))

    # Build 3D grid: grid[layer][row][col] = level 0–3
    grid = np.zeros((layers, rows, cols), dtype=np.uint8)

    # Fiducial markers at all 4 corners of every layer (level 3 = full power)
    for layer in range(layers):
        for ry, rx in [
            (0, 0),
            (0, cols - FIDUCIAL_SIZE),
            (rows - FIDUCIAL_SIZE, 0),
            (rows - FIDUCIAL_SIZE, cols - FIDUCIAL_SIZE),
        ]:
            grid[layer, ry:ry + FIDUCIAL_SIZE, rx:rx + FIDUCIAL_SIZE] = 3

    origin_r = FIDUCIAL_SIZE + BORDER
    origin_c = FIDUCIAL_SIZE + BORDER
    sym_idx = 0
    for layer in range(layers):
        for row in range(origin_r, origin_r + dr):
            for col in range(origin_c, origin_c + dc):
                grid[layer, row, col] = payload_symbols[sym_idx]
                sym_idx += 1

    # Optionally render per-layer PNGs (used by test_pipeline.py 3D test)
    layer_pngs = []
    if render_layers:
        base_dir = os.path.dirname(output_path) or '.'
        base_name = os.path.splitext(os.path.basename(output_path))[0]
        layers_dir = os.path.join(base_dir, base_name + '_layers')
        os.makedirs(layers_dir, exist_ok=True)
        for i in range(layers):
            png_path = os.path.join(layers_dir, f'layer_{i:02d}.png')
            render_layer_png(grid[i], cols, rows, png_path, levels=levels)
            layer_pngs.append(png_path)
        print(f"    Layers   : {layers} PNGs → {layers_dir}/")

    # Build STL files
    stl_files = []
    base = os.path.splitext(output_path)[0]

    if levels == 2:
        all_tris = []
        voxel_size = xy_pitch * VOXEL_FRACTION[1]
        voxel_count = 0
        for layer in range(layers):
            z = layer * z_pitch
            for row in range(rows):
                y = row * xy_pitch
                for col in range(cols):
                    if grid[layer, row, col]:
                        x = col * xy_pitch
                        all_tris.extend(_cube_tris(x, y, z, voxel_size))
                        voxel_count += 1
        write_binary_stl(output_path, all_tris, label='binary')
        stl_files = [(output_path, voxel_count, 1)]
        print(f"✅  3D Encoded (binary): {input_path}")
    else:
        level_names = {1: 'small', 2: 'medium', 3: 'large'}
        for target_level in [1, 2, 3]:
            tris = []
            voxel_size = xy_pitch * VOXEL_FRACTION[target_level]
            count = 0
            for layer in range(layers):
                z = layer * z_pitch
                for row in range(rows):
                    y = row * xy_pitch
                    for col in range(cols):
                        if grid[layer, row, col] == target_level:
                            x = col * xy_pitch
                            tris.extend(_cube_tris(x, y, z, voxel_size))
                            count += 1
            if tris:
                stl_path = f"{base}_L{target_level}_{level_names[target_level]}.stl"
                write_binary_stl(stl_path, tris, label=level_names[target_level])
                stl_files.append((stl_path, count, target_level))
        print(f"✅  3D Encoded (True 5D): {input_path}")

    # Write disc.json sidecar
    disc_json_path = base + '_disc.json'
    disc = {
        'format': '3D',
        'magic': MAGIC_3D_5D.hex() if levels >= 2 else MAGIC_3D_BINARY.hex(),
        'cols': cols,
        'rows': rows,
        'layers': layers,
        'ecc': ecc,
        'levels': levels,
        'xy_pitch_mm': xy_pitch,
        'z_pitch_mm': z_pitch,
        'source_file': os.path.basename(input_path),
        'source_crc32': f'{crc32:08X}',
        'stl_files': [s[0] for s in stl_files],
        'layer_pngs_dir': (layer_pngs[0].rsplit('/', 1)[0] if layer_pngs else None),
    }
    with open(disc_json_path, 'w') as f:
        json.dump(disc, f, indent=2)

    fill = len(file_to_symbols(rs_payload, levels)) / capacity_symbols * 100
    vol_x = cols * xy_pitch
    vol_y = rows * xy_pitch
    vol_z = layers * z_pitch
    capacity_bits = capacity_symbols * bpp

    print(f"    File     : {file_size} bytes  |  CRC32: {crc32:08X}")
    print(f"    Levels   : {levels} ({bpp} bits/position) — Dimension 5 = voxel size")
    print(f"    RS ECC   : {ecc} symbols/block  →  corrects up to {ecc//2} byte errors/block")
    print(f"    RS size  : {len(raw_payload)}B raw → {len(rs_payload)}B with ECC")
    print(f"    Grid     : {cols}×{rows}×{layers} layers  |  {fill:.1f}% full")
    print(f"    Capacity : {capacity_bits//8} bytes @ {levels}-level (vs {capacity_bits//8//bpp}B binary)")
    print(f"    Sidecar  : {disc_json_path}")
    print()

    if levels == 4:
        print(f"📐  xTool F2 Ultra — True 5D Inner Engraving (3 passes):")
        print(f"    Volume   : {vol_x:.1f}×{vol_y:.1f}×{vol_z:.1f} mm")
        print()
        power_map = {1: '50–60%', 2: '65–75%', 3: '80–90%'}
        for stl_path, count, lv in stl_files:
            stl_mb = os.path.getsize(stl_path) / 1024 / 1024
            name = ['', 'small', 'medium', 'large'][lv]
            print(f"    Pass L{lv} ({name:6s}): {stl_path}")
            print(f"             {count:,} voxels  |  {stl_mb:.1f} MB  |  Power: {power_map[lv]}  |  Speed: 500 mm/s")
        print()
        print(f"    ⚠️  Engrave all 3 STL files without moving the crystal between passes.")
        print(f"    Decode with: python3 decode_ssle_3d.py --disc {disc_json_path}")
        print(f"             or: python3 decode_ssle_3d.py --cols {cols} --rows {rows} --layers {layers} --ecc {ecc} --levels {levels}")
    else:
        stl_path, count, _ = stl_files[0]
        stl_mb = os.path.getsize(stl_path) / 1024 / 1024
        print(f"📐  xTool F2 Ultra — Inner Engraving:")
        print(f"    STL      : {stl_path}  ({stl_mb:.1f} MB,  {count:,} voxels)")
        print(f"    Volume   : {vol_x:.1f}×{vol_y:.1f}×{vol_z:.1f} mm")
        print(f"    Power    : 60–70%  |  Speed: 500 mm/s  |  Z step: {z_pitch:.2f} mm")
        print(f"    Decode with: python3 decode_ssle_3d.py --disc {disc_json_path}")

    return layer_pngs  # returned for use by test_pipeline.py


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Encode a file to 3D voxel STL(s) for xTool F2 Ultra UV inner engraving'
    )
    parser.add_argument('input_file', nargs='?',
                        help='File to encode (omit with --capacity for capacity calc only)')
    parser.add_argument('--output', '-o',
                        help='Output STL base path (default: <input>_voxel.stl)')
    parser.add_argument('--cols',     type=int,   default=DEFAULT_COLS)
    parser.add_argument('--rows',     type=int,   default=DEFAULT_ROWS)
    parser.add_argument('--layers',   type=int,   default=DEFAULT_LAYERS,
                        help=f'Z layers (default: {DEFAULT_LAYERS})')
    parser.add_argument('--xy-pitch', type=float, default=DEFAULT_XY_PITCH_MM,
                        help=f'XY dot pitch in mm (default: {DEFAULT_XY_PITCH_MM} = 100µm)')
    parser.add_argument('--z-pitch',  type=float, default=DEFAULT_Z_PITCH_MM,
                        help=f'Z layer spacing in mm (default: {DEFAULT_Z_PITCH_MM} = 500µm)')
    parser.add_argument('--ecc',      type=int,   default=DEFAULT_ECC,
                        help=f'Reed-Solomon ECC symbols (default: {DEFAULT_ECC})')
    parser.add_argument('--levels',   type=int,   default=DEFAULT_LEVELS, choices=[2, 4],
                        help='Voxel levels: 4=True 5D (2 bits/pos, default), 2=binary')
    parser.add_argument('--render-layers', action='store_true',
                        help='Also emit per-layer grayscale PNGs (used by 3D software test)')
    parser.add_argument('--capacity', action='store_true',
                        help='Print capacity for this grid and exit (no input file needed)')
    args = parser.parse_args()

    if args.capacity:
        print_capacity(args.cols, args.rows, args.layers, args.ecc,
                       args.xy_pitch, args.z_pitch, args.levels)
        sys.exit(0)

    if not args.input_file:
        parser.error('input_file is required (or use --capacity)')
    if not os.path.exists(args.input_file):
        print(f"ERROR: File not found: {args.input_file}")
        sys.exit(1)

    out = args.output or os.path.splitext(args.input_file)[0] + '_voxel.stl'
    encode(args.input_file, args.cols, args.rows, args.layers,
           args.xy_pitch, args.z_pitch, out, args.ecc, args.levels,
           render_layers=args.render_layers)
