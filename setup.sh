#!/bin/bash
# setup.sh — one-time Pi-side install. Run after git clone.
# Works on Raspberry Pi 5 with Raspberry Pi OS (Bookworm or later).

set -e

echo "[setup] Creating runtime directories..."
mkdir -p raw_scattering raw_scattering/layers output

echo "[setup] Making scripts executable..."
chmod +x run_reader.sh setup.sh

echo "[setup] Installing Python dependencies..."
pip3 install -r requirements.txt

echo ""
echo "[setup] Done."
echo ""
echo "  Verify software pipeline (no hardware needed):"
echo "    python3 test_pipeline.py"
echo ""
echo "  2D encode → engrave → read:"
echo "    python3 encode_ssle.py myfile.txt   # on laptop"
echo "    ./run_reader.sh                      # on Pi after engraving"
echo ""
echo "  3D encode (STL → xTool Studio):"
echo "    python3 encode_ssle_3d.py myfile.txt --layers 5"
echo ""
echo "  Stage test (simulation mode):"
echo "    python3 stage_control.py --sim --x 10 --y 10"
echo ""
