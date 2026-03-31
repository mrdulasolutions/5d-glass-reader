#!/usr/bin/env python3
"""
encode_ssle_3d.py — Encode any file to a 3D voxel STL for xTool F2 Ultra UV
inner engraving (true volumetric data storage across multiple Z-depth layers).

xTool Studio accepts STL/OBJ/3MF directly for inner engraving. This encoder
outputs a binary STL where each "1" bit is a tiny cube voxel at its 3D
coordinate. xTool's inner engraving mode fires the laser at each voxel's
position inside the glass at the correct X, Y, and Z depth — no external
slicing or conversion needed.

Capacity vs. 2D flat PNG encoder:
    2D (encode_ssle.py)    : ~61 KB at 100µm XY pitch, 70×70mm area
    3D (this file), 5 layers: ~306 KB  (5×)
    3D, 10 layers           : ~612 KB  (10×)
    3D, 20 layers           : ~1.2 MB  (20×) — aggressive, needs good focus

Reader note: Decoding a 3D disc requires captures at multiple Z focal depths.
  See decode_ssle_3d.py. Hardware: Pi HQ camera + lens with Z-adjustable focus
  or motorized Z stage. This is the v0.3 hardware upgrade path.

Usage:
    python3 encode_ssle_3d.py myfile.txt
    python3 encode_ssle_3d.py myfile.txt --cols 200 --rows 200 --layers 5
    python3 encode_ssle_3d.py myfile.txt --xy-pitch 0.1 --z-pitch 0.5
    python3 encode_ssle_3d.py --capacity --cols 700 --rows 700 --layers 10
"""

import argparse
import math
import os
import struct
import sys
import zlib

import numpy as np
from reedsolo import RSCodec

MAGIC = b'5DV\x01'         # 5D Volumetric v1
FIDUCIAL_SIZE = 3
BORDER = 1
MAX_FILENAME_LEN = 32
HEADER_BYTES = len(MAGIC) + 1 + MAX_FILENAME_LEN + 4 + 4   # 45 bytes
DEFAULT_ECC = 20
DEFAULT_COLS = 200
DEFAULT_ROWS = 200
DEFAULT_LAYERS = 5
DEFAULT_XY_PITCH_MM = 0.10   # 100 µm — safe for xTool F2 Ultra (20 µm spot)
DEFAULT_Z_PITCH_MM  = 0.50   # 500 µm between layers
VOXEL_FRACTION = 0.40        # voxel cube = 40% of pitch (avoids overlap)


# ── STL helpers ──────────────────────────────────────────────────────────────

def _cube_tris(cx, cy, cz, s):
    """12 triangles (vertex triples + normals) for a cube at (cx,cy,cz) size s."""
    h = s / 2
    v = [
        (cx-h, cy-h, cz-h), (cx+h, cy-h, cz-h),
        (cx+h, cy+h, cz-h), (cx-h, cy+h, cz-h),
        (cx-h, cy-h, cz+h), (cx+h, cy-h, cz+h),
        (cx+h, cy+h, cz+h), (cx-h, cy+h, cz+h),
    ]
    faces_normals = [
        ((v[0],v[2],v[1]), ( 0, 0,-1)),  # bottom
        ((v[0],v[3],v[2]), ( 0, 0,-1)),
        ((v[4],v[5],v[6]), ( 0, 0, 1)),  # top
        ((v[4],v[6],v[7]), ( 0, 0, 1)),
        ((v[0],v[1],v[5]), ( 0,-1, 0)),  # front
        ((v[0],v[5],v[4]), ( 0,-1, 0)),
        ((v[2],v[3],v[7]), ( 0, 1, 0)),  # back
        ((v[2],v[7],v[6]), ( 0, 1, 0)),
        ((v[0],v[4],v[7]), (-1, 0, 0)),  # left
        ((v[0],v[7],v[3]), (-1, 0, 0)),
        ((v[1],v[2],v[6]), ( 1, 0, 0)),  # right
        ((v[1],v[6],v[5]), ( 1, 0, 0)),
    ]
    return faces_normals


def write_binary_stl(path, all_tris_normals):
    """Write binary STL from list of (tri_vertices, normal) tuples."""
    n = len(all_tris_normals)
    with open(path, 'wb') as f:
        f.write(b'5DGlassVoxelSTL mrdulasolutions/5d-glass-reader'.ljust(80, b'\x00'))
        f.write(struct.pack('<I', n))
        for (tri, normal) in all_tris_normals:
            f.write(struct.pack('<3f', *normal))
            for vertex in tri:
                f.write(struct.pack('<3f', *vertex))
            f.write(b'\x00\x00')


# ── Encoding logic ────────────────────────────────────────────────────────────

def data_volume(cols, rows, layers):
    dc = cols - 2 * (FIDUCIAL_SIZE + BORDER)
    dr = rows - 2 * (FIDUCIAL_SIZE + BORDER)
    return dc, dr, layers


def file_to_bits(data):
    bits = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits


def build_header(filename, file_size, crc32):
    fname = os.path.basename(filename).encode()[:MAX_FILENAME_LEN]
    return (
        MAGIC
        + bytes([len(fname)])
        + fname.ljust(MAX_FILENAME_LEN, b'\x00')
        + struct.pack('>I', file_size)
        + struct.pack('>I', crc32)
    )


def print_capacity(cols, rows, layers, ecc, xy_pitch, z_pitch):
    dc, dr, _ = data_volume(cols, rows, layers)
    raw_bits = dc * dr * layers
    raw_bytes = raw_bits // 8
    rs_overhead = 1 + ecc / (255 - ecc)
    usable = int(raw_bytes / rs_overhead) - HEADER_BYTES
    vol_x = cols * xy_pitch
    vol_y = rows * xy_pitch
    vol_z = layers * z_pitch
    print(f"\n📦 3D Voxel Grid Capacity")
    print(f"   Grid      : {cols}×{rows}×{layers} layers")
    print(f"   XY pitch  : {xy_pitch*1000:.0f} µm   Z pitch: {z_pitch*1000:.0f} µm")
    print(f"   Volume    : {vol_x:.1f}×{vol_y:.1f}×{vol_z:.1f} mm  (fits in 70×70×150 mm inner area)")
    print(f"   Raw bits  : {raw_bits:,}  ({raw_bytes/1024:.1f} KB)")
    print(f"   RS ECC={ecc} : {ecc//2} byte errors/block correctable")
    print(f"   Usable    : ~{usable/1024:.1f} KB after header + ECC overhead")
    print(f"   vs 2D     : {layers}× the capacity of a flat dot-grid at same XY density\n")


def encode(input_path, cols, rows, layers, xy_pitch, z_pitch, output_path, ecc):
    with open(input_path, 'rb') as f:
        file_data = f.read()

    file_size = len(file_data)
    crc32 = zlib.crc32(file_data) & 0xFFFFFFFF
    header = build_header(input_path, file_size, crc32)
    raw_payload = header + file_data

    rs = RSCodec(ecc)
    rs_payload = bytes(rs.encode(raw_payload))
    payload_bits = file_to_bits(rs_payload)

    dc, dr, _ = data_volume(cols, rows, layers)
    capacity_bits = dc * dr * layers

    if len(payload_bits) > capacity_bits:
        needed_layers = math.ceil(len(payload_bits) / (dc * dr))
        print(f"ERROR: File too large.")
        print(f"  Capacity : {capacity_bits} bits ({capacity_bits//8} bytes)")
        print(f"  Needed   : {len(payload_bits)} bits")
        print(f"  Fix      : --layers {needed_layers}  (or increase --cols/--rows)")
        sys.exit(1)

    payload_bits += [0] * (capacity_bits - len(payload_bits))

    # Build 3D voxel grid: grid[layer][row][col]
    grid = np.zeros((layers, rows, cols), dtype=np.uint8)

    # Fiducial squares at all 4 corners of every layer
    for layer in range(layers):
        for ry, rx in [
            (0, 0),
            (0, cols - FIDUCIAL_SIZE),
            (rows - FIDUCIAL_SIZE, 0),
            (rows - FIDUCIAL_SIZE, cols - FIDUCIAL_SIZE),
        ]:
            grid[layer, ry:ry+FIDUCIAL_SIZE, rx:rx+FIDUCIAL_SIZE] = 1

    # Fill data: layer-major order
    origin_r = FIDUCIAL_SIZE + BORDER
    origin_c = FIDUCIAL_SIZE + BORDER
    bit_idx = 0
    for layer in range(layers):
        for row in range(origin_r, origin_r + dr):
            for col in range(origin_c, origin_c + dc):
                grid[layer, row, col] = payload_bits[bit_idx]
                bit_idx += 1

    # Build STL triangles
    voxel_size = xy_pitch * VOXEL_FRACTION
    all_tris = []
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

    write_binary_stl(output_path, all_tris)

    stl_mb = os.path.getsize(output_path) / 1024 / 1024
    fill = len(file_to_bits(rs_payload)) / capacity_bits * 100
    vol_x = cols * xy_pitch
    vol_y = rows * xy_pitch
    vol_z = layers * z_pitch

    print(f"✅  Encoded  : {input_path}")
    print(f"    File     : {file_size} bytes  |  CRC32: {crc32:08X}")
    print(f"    RS ECC   : {ecc} symbols/block  →  corrects up to {ecc//2} byte errors/block")
    print(f"    Grid     : {cols}×{rows}×{layers} layers  |  {fill:.1f}% full")
    print(f"    Voxels   : {voxel_count:,} dots encoded")
    print(f"    STL      : {output_path}  ({stl_mb:.1f} MB,  {len(all_tris):,} triangles)")
    print()
    print(f"📐  xTool F2 Ultra — Inner Engraving settings:")
    print(f"    Software : xTool Studio → Import → {output_path}")
    print(f"    Mode     : Inner Engraving (3D)")
    print(f"    Scale    : model is {vol_x:.1f}×{vol_y:.1f}×{vol_z:.1f} mm — fits in 70×70×150 mm area")
    print(f"    Medium   : K9 crystal (recommended for calibration) or JGS2 fused silica")
    print(f"    Power    : start 60–70%  |  Speed: 500 mm/s  |  Z step: {z_pitch:.2f} mm")
    print(f"    Focus    : auto-focus per Z layer (xTool Studio handles this)")
    print()
    print(f"    Decode with: python3 decode_ssle_3d.py --cols {cols} --rows {rows} --layers {layers} --ecc {ecc}")
    print(f"    Reader   : Pi HQ camera + Z-adjustable focus (motorized Z stage for v0.3)")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Encode a file to a 3D voxel STL for xTool F2 Ultra UV inner engraving'
    )
    parser.add_argument('input_file', nargs='?',
                        help='File to encode (omit with --capacity for capacity calc only)')
    parser.add_argument('--output', '-o',
                        help='Output STL path (default: <input>_voxel.stl)')
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
    parser.add_argument('--capacity', action='store_true',
                        help='Print capacity for this grid and exit (no input file needed)')
    args = parser.parse_args()

    if args.capacity:
        print_capacity(args.cols, args.rows, args.layers, args.ecc, args.xy_pitch, args.z_pitch)
        sys.exit(0)

    if not args.input_file:
        parser.error('input_file is required (or use --capacity)')
    if not os.path.exists(args.input_file):
        print(f"ERROR: File not found: {args.input_file}")
        sys.exit(1)

    out = args.output or os.path.splitext(args.input_file)[0] + '_voxel.stl'
    encode(args.input_file, args.cols, args.rows, args.layers,
           args.xy_pitch, args.z_pitch, out, args.ecc)
