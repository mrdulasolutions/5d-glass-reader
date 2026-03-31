#!/bin/bash
# setup.sh — one-time Pi-side install. Run after git clone.

set -e

echo "[setup] Creating runtime directories..."
mkdir -p raw_scattering output

echo "[setup] Making scripts executable..."
chmod +x run_reader.sh setup.sh

echo "[setup] Installing Python dependencies..."
pip3 install -r requirements.txt

echo "[setup] Done. Run ./run_reader.sh to start a capture."
