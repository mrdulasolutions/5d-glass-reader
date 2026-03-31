#!/usr/bin/env python3
"""
decode_ssle_3d.py — Decode a 3D-encoded glass disc back to the original file.
Companion to encode_ssle_3d.py.

Input: a directory of per-layer captured images (one PNG per Z depth),
named layer_00.png, layer_01.png, ... layer_NN.png.

Each image is processed with the same 2D dot-detection logic as decode_ssle.py,
then all layer bit-streams are interleaved in layer-major order and RS-decoded.

Hardware needed for 3D reading:
    - Pi HQ camera (same as 2D setup)
    - Z-adjustable focus: either a motorized Z stage or a liquid-lens module
    - Capture one image per Z depth, spaced by the same z-pitch used during encoding

Quick workflow:
    1. Mount disc under camera.
    2. For each Z depth: adjust focus, run capture_scattering.py, save as layer_NN.png
       (scan_disc.py --z-layers N automates this when Z stage is available)
    3. python3 decode_ssle_3d.py layers/ --cols 200 --rows 200 --layers 5

Usage:
    python3 decode_ssle_3d.py layers/              # default 200x200x5
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

MAGIC = b'5DV\x01'
FIDUCIAL_SIZE = 3
BORDER = 1
MAX_FILENAME_LEN = 32
HEADER_BYTES = len(MAGIC) + 1 + MAX_FILENAME_LEN + 4 + 4
DEFAULT_ECC = 20


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
    tl = min(candidates, key=lambda p: p[0]**2 + p[1]**2)
    tr = min(candidates, key=lambda p: (p[0]-iw)**2 + p[1]**2)
    bl = min(candidates, key=lambda p: p[0]**2 + (p[1]-ih)**2)
    br = min(candidates, key=lambda p: (p[0]-iw)**2 + (p[1]-ih)**2)
    if len({tl, tr, bl, br}) < 4:
        return None
    return tl, tr, bl, br


def extract_layer_bits(image_path, cols, rows, threshold):
    """Extract data bits from a single layer image. Returns list of bits."""
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
        dst = np.float32([[0,0],[side,0],[0,side],[side,side]])
        M = cv2.getPerspectiveTransform(src, dst)
        corrected = cv2.warpPerspective(img, M, (side, side))
        _, thresh = cv2.threshold(corrected, threshold, 255, cv2.THRESH_BINARY_INV)
    else:
        corrected = img

    dc = cols - 2 * (FIDUCIAL_SIZE + BORDER)
    dr = rows - 2 * (FIDUCIAL_SIZE + BORDER)
    origin_r = FIDUCIAL_SIZE + BORDER
    origin_c = FIDUCIAL_SIZE + BORDER
    cell_w = corrected.shape[1] / cols
    cell_h = corrected.shape[0] / rows

    bits = []
    for row in range(origin_r, origin_r + dr):
        for col in range(origin_c, origin_c + dc):
            cx = min(int((col + 0.5) * cell_w), corrected.shape[1]-1)
            cy = min(int((row + 0.5) * cell_h), corrected.shape[0]-1)
            region = thresh[max(0,cy-2):cy+3, max(0,cx-2):cx+3]
            bits.append(1 if region.mean() > 127 else 0)
    return bits


def bits_to_bytes(bits):
    result = bytearray()
    for i in range(0, len(bits) - 7, 8):
        byte = 0
        for b in bits[i:i+8]:
            byte = (byte << 1) | b
        result.append(byte)
    return bytes(result)


def decode(layers_dir, output_dir, cols, rows, n_layers, threshold, ecc):
    os.makedirs(output_dir, exist_ok=True)

    # Find layer images
    layer_files = sorted(glob.glob(os.path.join(layers_dir, 'layer_*.png')))
    if not layer_files:
        # Fallback: any PNG in directory, sorted
        layer_files = sorted(glob.glob(os.path.join(layers_dir, '*.png')))
    if not layer_files:
        print(f"ERROR: No PNG images found in {layers_dir}")
        print(f"       Expected: layer_00.png, layer_01.png, ... (one per Z depth)")
        sys.exit(1)

    if len(layer_files) < n_layers:
        print(f"WARNING: found {len(layer_files)} layer images, expected {n_layers}")
        print(f"         Proceeding with {len(layer_files)} layers")
        n_layers = len(layer_files)

    print(f"Layers   : {n_layers} images from {layers_dir}")

    # Extract bits from all layers
    all_bits = []
    for i, fpath in enumerate(layer_files[:n_layers]):
        print(f"  Layer {i:02d}: {os.path.basename(fpath)}", end='  ')
        bits = extract_layer_bits(fpath, cols, rows, threshold)
        if bits is None:
            print("SKIP")
            continue
        all_bits.extend(bits)
        print(f"({len(bits)} bits)")

    print(f"Total    : {len(all_bits)} bits extracted")

    raw_bytes = bits_to_bytes(all_bits)

    # Reed-Solomon decode
    rs = RSCodec(ecc)
    try:
        decoded_bytes, _, errata = rs.decode(raw_bytes)
        decoded_bytes = bytes(decoded_bytes)
        corrections = len(errata) if errata else 0
        print(f"RS ECC   : ✅ corrected {corrections} byte error(s)" if corrections
              else "RS ECC   : ✅ no errors detected")
    except ReedSolomonError as e:
        print(f"RS ECC   : ❌ {e}")
        print("           Try --threshold, --cols, --rows, --layers, or check Z-focus alignment")
        sys.exit(1)

    if len(decoded_bytes) < HEADER_BYTES or decoded_bytes[:4] != MAGIC:
        print(f"ERROR    : Bad magic {decoded_bytes[:4]!r} — wrong parameters or misaligned grid")
        sys.exit(1)

    fname_len = decoded_bytes[4]
    fname = decoded_bytes[5:5+fname_len].decode('utf-8', errors='replace')
    off = 5 + MAX_FILENAME_LEN
    file_size = struct.unpack('>I', decoded_bytes[off:off+4])[0]
    stored_crc = struct.unpack('>I', decoded_bytes[off+4:off+8])[0]

    file_data = decoded_bytes[HEADER_BYTES:HEADER_BYTES+file_size]
    actual_crc = zlib.crc32(file_data) & 0xFFFFFFFF
    crc_ok = actual_crc == stored_crc

    out_name = fname if fname else 'decoded_file.bin'
    out_path = os.path.join(output_dir, out_name)
    with open(out_path, 'wb') as f:
        f.write(file_data)

    print()
    print("=== 3D Decode Result ===")
    print(f"  Filename : {fname or '(none)'}")
    print(f"  Size     : {file_size} bytes")
    print(f"  CRC32    : {'✅ PASS' if crc_ok else '❌ FAIL'}")
    print(f"  Output   : {out_path}")
    print()
    if crc_ok:
        print("🎉 SUCCESS — 3D glass voxel data recovered!")
    else:
        print("⚠️  RS passed but CRC failed — check Z-focus alignment between layers.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Decode a 3D-encoded SSLE glass disc from per-layer images'
    )
    parser.add_argument('layers_dir', nargs='?', default='raw_scattering/layers',
                        help='Directory of layer_NN.png images (default: raw_scattering/layers)')
    parser.add_argument('--output', '-o', default='output')
    parser.add_argument('--cols',      type=int, default=200)
    parser.add_argument('--rows',      type=int, default=200)
    parser.add_argument('--layers',    type=int, default=5,
                        help='Number of Z layers — must match encoder (default: 5)')
    parser.add_argument('--threshold', type=int, default=80)
    parser.add_argument('--ecc',       type=int, default=DEFAULT_ECC)
    args = parser.parse_args()

    decode(args.layers_dir, args.output, args.cols, args.rows,
           args.layers, args.threshold, args.ecc)
