#!/usr/bin/env python3
"""
decode_ssle.py — Decode a scanned glass disc image back to the original file.
Companion to encode_ssle.py. Use matching --cols / --rows values.

Usage:
    python3 decode_ssle.py
    python3 decode_ssle.py raw_scattering/capture.png --cols 200 --rows 200
    python3 decode_ssle.py capture.png --threshold 100 --cols 400 --rows 400
"""

import argparse
import os
import struct
import sys
import zlib

import cv2
import numpy as np

MAGIC = b'5DG\x01'
FIDUCIAL_SIZE = 3
BORDER = 1
MAX_FILENAME_LEN = 32
HEADER_BYTES = len(MAGIC) + 1 + MAX_FILENAME_LEN + 4 + 4  # 45


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

    h, w = thresh.shape
    tl = min(candidates, key=lambda p: p[0] ** 2 + p[1] ** 2)
    tr = min(candidates, key=lambda p: (p[0] - w) ** 2 + p[1] ** 2)
    bl = min(candidates, key=lambda p: p[0] ** 2 + (p[1] - h) ** 2)
    br = min(candidates, key=lambda p: (p[0] - w) ** 2 + (p[1] - h) ** 2)

    # Sanity: all 4 must be distinct
    if len({tl, tr, bl, br}) < 4:
        return None
    return tl, tr, bl, br


def bits_to_bytes(bits):
    result = bytearray()
    for i in range(0, len(bits) - 7, 8):
        byte = 0
        for b in bits[i:i + 8]:
            byte = (byte << 1) | b
        result.append(byte)
    return bytes(result)


def decode(image_path, output_dir, grid_cols, grid_rows, threshold):
    os.makedirs(output_dir, exist_ok=True)

    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        print(f"ERROR: Could not load image: {image_path}")
        sys.exit(1)

    print(f"Loaded  : {image_path}  ({img.shape[1]}×{img.shape[0]} px)")

    # Invert: we want engraved dots (dark) → white in thresh
    _, thresh = cv2.threshold(img, threshold, 255, cv2.THRESH_BINARY_INV)

    # Perspective correction from fiducials
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
        print("Warning : fiducials not found — skipping perspective correction")
        corrected = img

    # Sample grid dots
    cell_w = corrected.shape[1] / grid_cols
    cell_h = corrected.shape[0] / grid_rows
    origin_row = FIDUCIAL_SIZE + BORDER
    origin_col = FIDUCIAL_SIZE + BORDER
    dcols = grid_cols - 2 * (FIDUCIAL_SIZE + BORDER)
    drows = grid_rows - 2 * (FIDUCIAL_SIZE + BORDER)

    bits = []
    for row in range(origin_row, origin_row + drows):
        for col in range(origin_col, origin_col + dcols):
            cx = int((col + 0.5) * cell_w)
            cy = int((row + 0.5) * cell_h)
            cy = min(cy, corrected.shape[0] - 1)
            cx = min(cx, corrected.shape[1] - 1)
            region = thresh[max(0, cy - 2):cy + 3, max(0, cx - 2):cx + 3]
            bits.append(1 if region.mean() > 127 else 0)

    print(f"Extracted: {len(bits)} bits from {dcols}×{drows} data area")

    all_bytes = bits_to_bytes(bits)

    # Validate magic
    if len(all_bytes) < HEADER_BYTES or all_bytes[:4] != MAGIC:
        print(f"ERROR: Bad magic {all_bytes[:4]!r} — grid misaligned or wrong --cols/--rows")
        print("       Try adjusting --threshold, --cols, --rows to match encoder settings")
        sys.exit(1)

    # Parse header
    fname_len = all_bytes[4]
    fname = all_bytes[5:5 + fname_len].decode('utf-8', errors='replace')
    off = 5 + MAX_FILENAME_LEN
    file_size = struct.unpack('>I', all_bytes[off:off + 4])[0]
    stored_crc = struct.unpack('>I', all_bytes[off + 4:off + 8])[0]

    file_data = all_bytes[HEADER_BYTES:HEADER_BYTES + file_size]
    actual_crc = zlib.crc32(file_data) & 0xFFFFFFFF
    crc_ok = actual_crc == stored_crc

    out_name = fname if fname else 'decoded_file.bin'
    out_path = os.path.join(output_dir, out_name)
    with open(out_path, 'wb') as f:
        f.write(file_data)

    print()
    print(f"=== Decode Result ===")
    print(f"  Filename : {fname or '(none)'}")
    print(f"  Size     : {file_size} bytes")
    print(f"  CRC32    : {'✅ PASS' if crc_ok else '❌ FAIL — data corruption detected'}")
    print(f"  Output   : {out_path}")
    print()
    if crc_ok:
        print("🎉 SUCCESS — file recovered from glass!")
    else:
        print("⚠️  Partial recovery. Try --threshold <value> to tune binarization.")
        print("   Hint: if dots are dim, lower threshold (e.g. --threshold 60)")
        print("         if background noise, raise it (e.g. --threshold 120)")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Decode a scanned SSLE glass disc image back to the original file'
    )
    parser.add_argument('image', nargs='?', default='raw_scattering/capture.png',
                        help='Captured image path (default: raw_scattering/capture.png)')
    parser.add_argument('--output', '-o', default='output',
                        help='Output directory (default: output)')
    parser.add_argument('--cols', type=int, default=200,
                        help='Grid columns — must match encoder (default: 200)')
    parser.add_argument('--rows', type=int, default=200,
                        help='Grid rows — must match encoder (default: 200)')
    parser.add_argument('--threshold', type=int, default=80,
                        help='Binarization threshold 0–255 (default: 80)')
    args = parser.parse_args()

    decode(args.image, args.output, args.cols, args.rows, args.threshold)
