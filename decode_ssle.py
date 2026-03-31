#!/usr/bin/env python3
"""
decode_ssle.py — Decode a scanned glass disc image back to the original file.
Companion to encode_ssle.py. Reed-Solomon error correction applied automatically.

Supports all format versions (auto-detected from magic bytes):
  5DG\\x02  — v2 legacy binary (1 bit/position, 45-byte header)
  5DG\\x03  — v3 True 5D, ECC not in header (46-byte header)
  5DG\\x04  — v4 True 5D, ECC stored in header (47-byte header) ← current

If a disc.json sidecar is available (written by encode_ssle.py), pass it with
--disc and the decoder will configure itself automatically.

If calibration.json is present in the working directory (written by
calibrate_glass.py), brightness thresholds are loaded from it automatically.

Usage:
    python3 decode_ssle.py --disc myfile_5d_disc.json
    python3 decode_ssle.py raw_scattering/capture.png --cols 200 --rows 200
    python3 decode_ssle.py capture.png --levels 4 --ecc 40
    python3 decode_ssle.py capture.png --levels 2     # legacy binary
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
from reedsolo import RSCodec, ReedSolomonError

from constants import (
    MAGIC_2D_BINARY, MAGIC_2D_5D_V3, MAGIC_2D_5D,
    FIDUCIAL_SIZE, BORDER, MAX_FILENAME_LEN,
    HEADER_BYTES_LEGACY, HEADER_BYTES_OLD_5D, HEADER_BYTES,
    DEFAULT_ECC, DEFAULT_LEVELS,
    bits_per_position, load_calibration, load_disc_params,
    DEFAULT_LEVEL_THRESHOLDS,
)


def classify_level(mean_brightness, levels, thresholds):
    """Map raw pixel brightness to a symbol level using per-glass thresholds."""
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
    """Find 4 corner fiducial squares. Returns (tl, tr, bl, br) centers or None."""
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


def decode(image_path, output_dir, grid_cols, grid_rows, threshold, ecc, levels,
           calibration_path='calibration.json'):
    os.makedirs(output_dir, exist_ok=True)

    thresholds = load_calibration(calibration_path)

    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        print(f"ERROR: Could not load image: {image_path}")
        sys.exit(1)

    print(f"Loaded   : {image_path}  ({img.shape[1]}×{img.shape[0]} px)")
    print(f"Mode     : {levels}-level ({'True 5D' if levels == 4 else 'binary'})  —  {bits_per_position(levels)} bits/position")

    _, thresh = cv2.threshold(img, threshold, 255, cv2.THRESH_BINARY_INV)

    fiducials = find_fiducials(thresh)
    if fiducials:
        tl, tr, bl, br = fiducials
        print(f"Fiducials: TL={tl} TR={tr} BL={bl} BR={br}")
        side = max(img.shape)
        src = np.float32([tl, tr, bl, br])
        dst = np.float32([[0, 0], [side, 0], [0, side], [side, side]])
        M = cv2.getPerspectiveTransform(src, dst)
        corrected = cv2.warpPerspective(img, M, (side, side))
        _, thresh = cv2.threshold(corrected, threshold, 255, cv2.THRESH_BINARY_INV)
    else:
        print("Warning  : fiducials not found — skipping perspective correction")
        corrected = img

    cell_w = corrected.shape[1] / grid_cols
    cell_h = corrected.shape[0] / grid_rows
    origin_row = FIDUCIAL_SIZE + BORDER
    origin_col = FIDUCIAL_SIZE + BORDER
    dcols = grid_cols - 2 * (FIDUCIAL_SIZE + BORDER)
    drows = grid_rows - 2 * (FIDUCIAL_SIZE + BORDER)

    symbols = []
    for row in range(origin_row, origin_row + drows):
        for col in range(origin_col, origin_col + dcols):
            cx = min(int((col + 0.5) * cell_w), corrected.shape[1] - 1)
            cy = min(int((row + 0.5) * cell_h), corrected.shape[0] - 1)
            region = corrected[max(0, cy - 2):cy + 3, max(0, cx - 2):cx + 3]
            # Use darkest pixel — robust to background blending.
            # For real glass captures where dots appear BRIGHT (raking light),
            # invert the image before passing to this decoder.
            dot_val = float(region.min()) if region.size > 0 else 255.0
            symbols.append(classify_level(dot_val, levels, thresholds))

    bpp = bits_per_position(levels)
    bits = symbols_to_bits(symbols, levels)
    print(f"Extracted: {len(symbols)} positions × {bpp} bits = {len(bits)} bits  ({dcols}×{drows} data area)")

    raw_bytes = bits_to_bytes(bits)

    # Reed-Solomon decode
    rs = RSCodec(ecc)
    try:
        decoded_bytes, _, errata = rs.decode(raw_bytes)
        decoded_bytes = bytes(decoded_bytes)
        corrections = len(errata) if errata else 0
        if corrections:
            print(f"RS ECC   : corrected {corrections} byte error(s)")
        else:
            print(f"RS ECC   : no errors detected")
    except ReedSolomonError as e:
        print(f"RS ECC   : too many errors to correct — {e}")
        print("           Adjust --threshold, --cols, --rows, or check alignment.")
        if levels == 4:
            print("           Also try: --levels 2  if disc was encoded in binary mode")
        print("           Hint: lower threshold if dots are dim; raise if background is noisy.")
        print("           For per-glass tuning run: python3 calibrate_glass.py --analyze scan.png")
        sys.exit(1)

    # Auto-detect format version from magic bytes
    magic = decoded_bytes[:4] if len(decoded_bytes) >= 4 else b''

    if magic == MAGIC_2D_5D:
        # v4: levels(1) + ecc(1) + fname_len(1) + fname(32) + size(4) + crc(4)
        header_bytes = HEADER_BYTES
        enc_levels = decoded_bytes[4]
        enc_ecc    = decoded_bytes[5]
        fname_len  = decoded_bytes[6]
        fname      = decoded_bytes[7:7 + fname_len].decode('utf-8', errors='replace')
        off        = 4 + 1 + 1 + 1 + MAX_FILENAME_LEN
        print(f"Format   : 5DG v4 (True 5D, {enc_levels}-level, ECC={enc_ecc})")

    elif magic == MAGIC_2D_5D_V3:
        # v3: levels(1) + fname_len(1) + fname(32) + size(4) + crc(4)
        header_bytes = HEADER_BYTES_OLD_5D
        enc_levels = decoded_bytes[4]
        enc_ecc    = ecc  # not stored; use whatever was passed in
        fname_len  = decoded_bytes[5]
        fname      = decoded_bytes[6:6 + fname_len].decode('utf-8', errors='replace')
        off        = 4 + 1 + 1 + MAX_FILENAME_LEN
        print(f"Format   : 5DG v3 (True 5D, {enc_levels}-level, ECC not in header)")

    elif magic == MAGIC_2D_BINARY:
        # v2: fname_len(1) + fname(32) + size(4) + crc(4)
        header_bytes = HEADER_BYTES_LEGACY
        enc_levels = 2
        enc_ecc    = ecc
        fname_len  = decoded_bytes[4]
        fname      = decoded_bytes[5:5 + fname_len].decode('utf-8', errors='replace')
        off        = 4 + 1 + MAX_FILENAME_LEN
        print(f"Format   : 5DG v2 (legacy binary)")
        if levels != 2:
            print(f"           Note: disc was binary-encoded — re-run with --levels 2 for best results")
    else:
        print(f"ERROR    : Bad magic {magic!r} — wrong --cols/--rows/--ecc or wrong --levels")
        if levels == 4:
            print(f"           Try: --levels 2  (legacy binary grid)")
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
    print("=== Decode Result ===")
    print(f"  Filename : {fname or '(none)'}")
    print(f"  Size     : {file_size} bytes")
    print(f"  CRC32    : {'PASS' if crc_ok else 'FAIL — data corruption'}")
    print(f"  Output   : {out_path}")
    print()
    if crc_ok:
        print("SUCCESS — file recovered from glass!")
    else:
        print("WARNING  : RS corrected errors but CRC still failed — severe corruption.")
        print("   Check camera focus, lighting, and disc alignment.")
        if levels == 4:
            print("   For multi-level: ensure xTool was set to Grayscale mode (not bitmap).")
            print("   Capture image should show distinct gray shades, not just black/white.")
            print("   Run: python3 calibrate_glass.py --analyze <scan> to auto-tune thresholds.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Decode a scanned SSLE glass disc image (True 5D or legacy binary)'
    )
    parser.add_argument('image', nargs='?', default='raw_scattering/capture.png',
                        help='Captured image path (default: raw_scattering/capture.png)')
    parser.add_argument('--disc', metavar='DISC_JSON',
                        help='disc.json sidecar (auto-sets cols/rows/ecc/levels)')
    parser.add_argument('--output', '-o', default='output',
                        help='Output directory (default: output)')
    parser.add_argument('--cols', type=int, default=200,
                        help='Grid columns — must match encoder (default: 200)')
    parser.add_argument('--rows', type=int, default=200,
                        help='Grid rows — must match encoder (default: 200)')
    parser.add_argument('--threshold', type=int, default=80,
                        help='Binarization threshold for fiducial detection 0–255 (default: 80)')
    parser.add_argument('--ecc', type=int, default=DEFAULT_ECC,
                        help=f'Reed-Solomon ECC symbols — must match encoder (default: {DEFAULT_ECC})')
    parser.add_argument('--levels', type=int, default=DEFAULT_LEVELS, choices=[2, 4],
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
            args.ecc    = params.get('ecc',    args.ecc)
            args.levels = params.get('levels', args.levels)
            print(f"[disc.json] cols={args.cols} rows={args.rows} ecc={args.ecc} levels={args.levels}")

    decode(args.image, args.output, args.cols, args.rows, args.threshold, args.ecc, args.levels,
           calibration_path=args.calibration)
