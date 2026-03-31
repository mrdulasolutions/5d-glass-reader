#!/usr/bin/env python3
"""
constants.py — Shared constants for all EternalDrive-IndieHack scripts.

Import from here rather than redefining per-file so all scripts
stay in sync when format or tuning values change.
"""

import json
import math
import os

# ── Format magic bytes ────────────────────────────────────────────────────────
# 2D (single-layer) formats
MAGIC_2D_BINARY  = b'5DG\x02'   # v2: legacy binary (1 bit/position, 45-byte header)
MAGIC_2D_5D_V3   = b'5DG\x03'   # v3: True 5D, ECC NOT in header (46-byte header)
MAGIC_2D_5D      = b'5DG\x04'   # v4: True 5D, ECC stored in header (47-byte header) ← current

# 3D (multi-layer / voxel) formats
MAGIC_3D_BINARY  = b'5DV\x01'   # v1: legacy binary (1 bit/position, 45-byte header)
MAGIC_3D_5D_V2   = b'5DV\x02'   # v2: True 5D, ECC NOT in header (46-byte header)
MAGIC_3D_5D      = b'5DV\x03'   # v3: True 5D, ECC stored in header (47-byte header) ← current

# ── Header sizes (bytes) ──────────────────────────────────────────────────────
# v2/v3 (legacy):  MAGIC(4) + fname_len(1) + fname(32) + size(4) + crc(4)         = 45
# v3/v2 (5D old):  MAGIC(4) + levels(1) + fname_len(1) + fname(32) + size(4) + crc(4) = 46
# v4/v3 (current): MAGIC(4) + levels(1) + ecc(1) + fname_len(1) + fname(32) + size(4) + crc(4) = 47
HEADER_BYTES_LEGACY   = 45   # 5DG\x02 / 5DV\x01
HEADER_BYTES_OLD_5D   = 46   # 5DG\x03 / 5DV\x02
HEADER_BYTES          = 47   # 5DG\x04 / 5DV\x03  ← current

# ── Grid layout ──────────────────────────────────────────────────────────────
FIDUCIAL_SIZE    = 3    # side of corner fiducial squares (in grid cells)
BORDER           = 1    # blank-cell gap between fiducial and data area
MAX_FILENAME_LEN = 32   # bytes reserved for filename in header

# ── Encoding defaults ─────────────────────────────────────────────────────────
DEFAULT_ECC    = 20   # Reed-Solomon ECC symbols per 255-byte block
DEFAULT_LEVELS = 4    # 4 gray levels → 2 bits/position (True 5D)

# ── Gray value map ────────────────────────────────────────────────────────────
# Level → pixel brightness written to the PNG
# xTool grayscale mode: brighter pixel → less dwell → smaller scattering bubble
GRAY = {0: 255, 1: 192, 2: 128, 3: 0}

# ── Brightness classification thresholds ─────────────────────────────────────
# When reading back: raw pixel brightness → level
# Midpoints between adjacent gray values:
#   255↔192 = 224,  192↔128 = 160,  128↔0 = 64
# Overridden at runtime if calibration.json is present.
DEFAULT_LEVEL_THRESHOLDS = [224, 160, 64]


def bits_per_position(levels: int) -> int:
    return int(math.log2(levels))


def load_calibration(cal_path: str = 'calibration.json') -> list:
    """
    Load per-glass brightness thresholds from calibration.json.
    Returns DEFAULT_LEVEL_THRESHOLDS if the file is absent or unreadable.
    """
    if os.path.exists(cal_path):
        try:
            with open(cal_path) as f:
                cal = json.load(f)
            thresholds = cal.get('level_thresholds', DEFAULT_LEVEL_THRESHOLDS)
            print(f"[calibration] Loaded thresholds from {cal_path}: {thresholds}")
            return thresholds
        except Exception as e:
            print(f"[calibration] Warning: could not read {cal_path}: {e}")
    return DEFAULT_LEVEL_THRESHOLDS


def load_disc_params(disc_json: str = 'disc.json') -> dict:
    """
    Load encoding parameters from a disc.json sidecar file.
    Returns None if the file is absent or unreadable.
    """
    if os.path.exists(disc_json):
        try:
            with open(disc_json) as f:
                return json.load(f)
        except Exception as e:
            print(f"[disc.json] Warning: could not read {disc_json}: {e}")
    return None
