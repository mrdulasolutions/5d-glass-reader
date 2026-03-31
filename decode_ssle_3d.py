#!/usr/bin/env python3
"""
decode_ssle_3d.py — Decode a 3D-encoded glass disc back to the original file.
Companion to encode_ssle_3d.py.

Input: a directory of per-layer captured images (one PNG per Z depth),
named layer_00.png, layer_01.png, ... layer_NN.png.

Supports all format versions (auto-detected from magic bytes):
  5DV\\x01  — v1 legacy 3D binary (1 bit/position, 45-byte header)
  5DV\\x02  — v2 True 5D 3D, ECC not in header (46-byte header)
  5DV\\x03  — v3 True 5D 3D, ECC stored in header (47-byte header) ← current

If a disc.json sidecar is available (written by encode_ssle_3d.py), pass it
with --disc and the decoder will configure itself automatically.

If calibration.json is present (written by calibrate_glass.py), brightness
thresholds are loaded from it automatically.

Hardware needed for 3D reading:
    - Pi HQ camera (same as 2D setup)
    - Z-adjustable focus: motorized Z stage or liquid-lens module
    - Capture one image per Z depth, spaced by the same z-pitch used during encoding

Quick workflow:
    1. Mount disc under camera.
    2. For each Z depth: adjust focus → capture_scattering.py → save as layer_NN.png
    3. python3 decode_ssle_3d.py --disc myfile_voxel_disc.json layers/

Usage:
    python3 decode_ssle_3d.py --disc myfile_voxel_disc.json layers/
    python3 decode_ssle_3d.py layers/              # default 200×200×5, 4-level
    python3 decode_ssle_3d.py layers/ --levels 2   # legacy binary
    python3 decode_ssle_3d.py layers/ --cols 400 --rows 400 --layers 10 --ecc 20
"""

import argparse
import glob
import os
import struct
import sys
import zlib

import cv2
import numpy as np
from reedsolo import RSCodec, ReedSolomonError

from constants import (
    MAGIC_3D_BINARY, MAGIC_3D_5D_V2, MAGIC_3D_5D,
    FIDUCIAL_SIZE, BORDER, MAX_FILENAME_LEN,
    HEADER_BYTES_LEGACY, HEADER_BYTES_OLD_5D, HEADER_BYTES,
    DEFAULT_ECC, DEFAULT_LEVELS,
    bits_per_position, load_calibration, load_disc_params,
    DEFAULT_LEVEL_THRESHOLDS,
)


def classify_level(mean_brightness, levels, thresholds):
    if levels == 2:
        return 0 if mean_brightness > 127 else 1
    t0, t1, t2 = thresholds
    if mean_brightness > t0:
        return 0
    if mean_brightness > t1:
        return 1
    if mean_brightness > t2:
        return 2
    return 3


def symbols_to_bits(symbols, levels):
    bpp = bits_per_position(levels)
    bits = []
    for sym in symbols:
        for i in range(bpp - 1, -1, -1):
            bits.append((sym >> i) & 1)
    return bits


def bits_to_bytes(bits):
    result = bytearray()
    for i in range(0, len(bits) - 7, 8):
        byte = 0
        for b in bits[i:i + 8]:
            byte = (byte << 1) | b
        result.append(byte)
    return bytes(result)


def find_fiducials(thresh):
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    candidates = []
    for cnt in contours[:30]:
        if cv2.contourArea(cnt) < 40:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        if 0.4 < w / max(h, 1) < 2.5:
            candidates.append((x + w // 2, y + h // 2))
    if len(candidates) < 4:
        return None
    ih, iw = thresh.shape
    tl = min(candidates, key=lambda p: p[0] ** 2 + p[1] ** 2)
    tr = min(candidates, key=lambda p: (p[0] - iw) ** 2 + p[1] ** 2)
    bl = min(candidates, key=lambda p: p[0] ** 2 + (p[1] - ih) ** 2)
    br = min(candidates, key=lambda p: (p[0] - iw) ** 2 + (p[1] - ih) ** 2)
    if len({tl, tr, bl, br}) < 4:
        return None
    return tl, tr, bl, br


def extract_layer_symbols(image_path, cols, rows, threshold, levels, thresholds):
    """Extract multi-level symbols from a single layer image."""
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        print(f"  ERROR: could not load {image_path}")
        return None

    _, thresh = cv2.threshold(img, threshold, 255, cv2.THRESH_BINARY_INV)

    fiducials = find_fiducials(thresh)
    if fiducials:
        tl, tr, bl, br = fiducials
        side = max(img.shape)
        src = np.float32([tl, tr, bl, br])
        dst = np.float32([[0, 0], [side, 0], [0, side], [side, side]])
        M = cv2.getPerspectiveTransform(src, dst)
        corrected = cv2.warpPerspective(img, M, (side, side))
    else:
        corrected = img

    dc = cols - 2 * (FIDUCIAL_SIZE + BORDER)
    dr = rows - 2 * (FIDUCIAL_SIZE + BORDER)
    origin_r = FIDUCIAL_SIZE + BORDER
    origin_c = FIDUCIAL_SIZE + BORDER
    cell_w = corrected.shape[1] / cols
    cell_h = corrected.shape[0] / rows

    symbols = []
    for row in range(origin_r, origin_r + dr):
        for col in range(origin_c, origin_c + dc):
            cx = min(int((col + 0.5) * cell_w), corrected.shape[1] - 1)
            cy = min(int((row + 0.5) * cell_h), corrected.shape[0] - 1)
            region = corrected[max(0, cy - 2):cy + 3, max(0, cx - 2):cx + 3]
            dot_val = float(region.min()) if region.size > 0 else 255.0
            symbols.append(classify_level(dot_val, levels, thresholds))
    return symbols


def decode(layers_dir, output_dir, cols, rows, n_layers, threshold, ecc, levels,
           calibration_path='calibration.json'):
    os.makedirs(output_dir, exist_ok=True)

    thresholds = load_calibration(calibration_path)

    layer_files = sorted(glob.glob(os.path.join(layers_dir, 'layer_*.png')))
    if not layer_files:
        layer_files = sorted(glob.glob(os.path.join(layers_dir, '*.png')))
    if not layer_files:
        print(f"ERROR: No PNG images found in {layers_dir}")
        print(f"       Expected: layer_00.png, layer_01.png, ... (one per Z depth)")
        sys.exit(1)

    if len(layer_files) < n_layers:
        print(f"WARNING: found {len(layer_files)} layer images, expected {n_layers}")
        n_layers = len(layer_files)

    bpp = bits_per_position(levels)
    print(f"Layers   : {n_layers} images from {layers_dir}")
    print(f"Mode     : {levels}-level ({'True 5D' if levels == 4 else 'binary'})  —  {bpp} bits/position")

    all_symbols = []
    for i, fpath in enumerate(layer_files[:n_layers]):
        print(f"  Layer {i:02d}: {os.path.basename(fpath)}", end='  ')
        syms = extract_layer_symbols(fpath, cols, rows, threshold, levels, thresholds)
        if syms is None:
            print("SKIP")
            continue
        all_symbols.extend(syms)
        print(f"({len(syms)} symbols)")

    bits = symbols_to_bits(all_symbols, levels)
    print(f"Total    : {len(all_symbols)} symbols × {bpp} bits = {len(bits)} bits extracted")

    raw_bytes = bits_to_bytes(bits)

    rs = RSCodec(ecc)
    try:
        decoded_bytes, _, errata = rs.decode(raw_bytes)
        decoded_bytes = bytes(decoded_bytes)
        corrections = len(errata) if errata else 0
        print(f"RS ECC   : corrected {corrections} byte error(s)" if corrections
              else "RS ECC   : no errors detected")
    except ReedSolomonError as e:
        print(f"RS ECC   : {e}")
        print("           Try --threshold, --cols, --rows, --layers, or check Z-focus alignment")
        if levels == 4:
            print("           Also try: --levels 2  if disc was binary-encoded")
        print("           For per-glass tuning run: python3 calibrate_glass.py --analyze scan.png")
        sys.exit(1)

    # Auto-detect format version from magic bytes
    magic = decoded_bytes[:4] if len(decoded_bytes) >= 4 else b''

    if magic == MAGIC_3D_5D:
        # v3: levels(1) + ecc(1) + fname_len(1) + fname(32) + size(4) + crc(4)
        header_bytes = HEADER_BYTES
        enc_levels = decoded_bytes[4]
        enc_ecc    = decoded_bytes[5]
        fname_len  = decoded_bytes[6]
        fname      = decoded_bytes[7:7 + fname_len].decode('utf-8', errors='replace')
        off        = 4 + 1 + 1 + 1 + MAX_FILENAME_LEN
        print(f"Format   : 5DV v3 (True 5D 3D, {enc_levels}-level, ECC={enc_ecc})")

    elif magic == MAGIC_3D_5D_V2:
        # v2: levels(1) + fname_len(1) + fname(32) + size(4) + crc(4)
        header_bytes = HEADER_BYTES_OLD_5D
        enc_levels = decoded_bytes[4]
        enc_ecc    = ecc
        fname_len  = decoded_bytes[5]
        fname      = decoded_bytes[6:6 + fname_len].decode('utf-8', errors='replace')
        off        = 4 + 1 + 1 + MAX_FILENAME_LEN
        print(f"Format   : 5DV v2 (True 5D 3D, {enc_levels}-level, ECC not in header)")

    elif magic == MAGIC_3D_BINARY:
        # v1: fname_len(1) + fname(32) + size(4) + crc(4)
        header_bytes = HEADER_BYTES_LEGACY
        enc_levels = 2
        enc_ecc    = ecc
        fname_len  = decoded_bytes[4]
        fname      = decoded_bytes[5:5 + fname_len].decode('utf-8', errors='replace')
        off        = 4 + 1 + MAX_FILENAME_LEN
        print(f"Format   : 5DV v1 (legacy 3D binary)")
        if levels != 2:
            print(f"           Note: disc was binary-encoded — re-run with --levels 2 for best results")
    else:
        print(f"ERROR    : Bad magic {magic!r} — wrong parameters or misaligned grid")
        if levels == 4:
            print(f"           Try: --levels 2  (legacy binary 3D)")
        sys.exit(1)

    if len(decoded_bytes) < header_bytes:
        print(f"ERROR    : Decoded payload too short ({len(decoded_bytes)} < {header_bytes})")
        sys.exit(1)

    file_size  = struct.unpack('>I', decoded_bytes[off:off + 4])[0]
    stored_crc = struct.unpack('>I', decoded_bytes[off + 4:off + 8])[0]

    file_data  = decoded_bytes[header_bytes:header_bytes + file_size]
    actual_crc = zlib.crc32(file_data) & 0xFFFFFFFF
    crc_ok     = actual_crc == stored_crc

    out_name = fname if fname else 'decoded_file.bin'
    out_path = os.path.join(output_dir, out_name)
    with open(out_path, 'wb') as f:
        f.write(file_data)

    print()
    print("=== 3D Decode Result ===")
    print(f"  Filename : {fname or '(none)'}")
    print(f"  Size     : {file_size} bytes")
    print(f"  CRC32    : {'PASS' if crc_ok else 'FAIL'}")
    print(f"  Output   : {out_path}")
    print()
    if crc_ok:
        print("SUCCESS — 3D glass voxel data recovered!")
    else:
        print("WARNING  : RS passed but CRC failed — check Z-focus alignment between layers.")
        if levels == 4:
            print("   For True 5D: capture must show distinct gray shades per layer.")
            print("   Ensure xTool was set to Grayscale inner engraving for all 3 passes.")
            print("   Run: python3 calibrate_glass.py --analyze <layer_00.png> to auto-tune.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Decode a 3D-encoded SSLE glass disc from per-layer images (True 5D or binary)'
    )
    parser.add_argument('layers_dir', nargs='?', default='raw_scattering/layers',
                        help='Directory of layer_NN.png images (default: raw_scattering/layers)')
    parser.add_argument('--disc', metavar='DISC_JSON',
                        help='disc.json sidecar (auto-sets cols/rows/layers/ecc/levels)')
    parser.add_argument('--output', '-o', default='output')
    parser.add_argument('--cols',      type=int, default=200)
    parser.add_argument('--rows',      type=int, default=200)
    parser.add_argument('--layers',    type=int, default=5,
                        help='Number of Z layers — must match encoder (default: 5)')
    parser.add_argument('--threshold', type=int, default=80,
                        help='Threshold for fiducial detection (default: 80)')
    parser.add_argument('--ecc',       type=int, default=DEFAULT_ECC)
    parser.add_argument('--levels',    type=int, default=DEFAULT_LEVELS, choices=[2, 4],
                        help='Dot levels: 4=True 5D grayscale (default), 2=legacy binary')
    parser.add_argument('--calibration', default='calibration.json',
                        help='Calibration file path (default: calibration.json)')
    args = parser.parse_args()

    # Auto-configure from disc.json if provided
    if args.disc:
        params = load_disc_params(args.disc)
        if params:
            args.cols   = params.get('cols',   args.cols)
            args.rows   = params.get('rows',   args.rows)
            args.layers = params.get('layers', args.layers)
            args.ecc    = params.get('ecc',    args.ecc)
            args.levels = params.get('levels', args.levels)
            if params.get('layer_pngs_dir') and args.layers_dir == 'raw_scattering/layers':
                args.layers_dir = params['layer_pngs_dir']
            print(f"[disc.json] cols={args.cols} rows={args.rows} layers={args.layers} ecc={args.ecc} levels={args.levels}")

    decode(args.layers_dir, args.output, args.cols, args.rows,
           args.layers, args.threshold, args.ecc, args.levels,
           calibration_path=args.calibration)
