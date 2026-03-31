#!/bin/bash
set -e

mkdir -p raw_scattering output

echo "[reader] Capturing glass disc..."
python3 capture_scattering.py

echo "[reader] Decoding SSLE dots..."
python3 decode_ssle.py

echo "[reader] Done. Results written to output/"
