#!/bin/bash
# run_reader.sh — capture polarized images and decode 5D optical data
# Run on Raspberry Pi 5. Requires: setup.sh to have been run first.

set -e

# Ensure runtime directories exist (idempotent)
mkdir -p raw_polarized output calibration

echo "[reader] Starting polarized capture..."
python3 capture_polarized.py

echo "[reader] Decoding 5D data..."
python3 decode_5d.py

echo "[reader] Done. Results written to output/"
