#!/bin/bash
# make_stl.sh — Encode any file to xTool-ready STL(s) for glass engraving
# Usage: bash make_stl.sh [file]
#
# Walks you through picking a file, choosing a K9 size, and runs the encoder.
# Outputs the exact xTool Studio steps to follow.
# A disc.json sidecar is written alongside the STLs — keep it with the disc.

set -e

BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
CYAN="\033[0;36m"
RED="\033[0;31m"
RESET="\033[0m"

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║   5D Glass Eternal Drive — STL Encoder       ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════════════════════╝${RESET}"
echo ""

# ── Step 1: Pick the file ─────────────────────────────────────────────────────

if [ -n "$1" ]; then
    INPUT="$1"
else
    echo -e "${CYAN}What file do you want to encode into glass?${RESET}"
    echo -e "  (drag and drop it into this terminal, or type the path)"
    echo -n "  File: "
    read -r INPUT
fi

INPUT="${INPUT%\"}"
INPUT="${INPUT#\"}"
INPUT="${INPUT% }"

if [ ! -f "$INPUT" ]; then
    echo -e "${RED}ERROR: File not found: $INPUT${RESET}"
    exit 1
fi

FILESIZE=$(python3 -c "import os; print(os.path.getsize('$INPUT'))")
FILENAME=$(python3 -c "import os; print(os.path.basename('$INPUT'))")
echo ""
echo -e "  File    : ${BOLD}$FILENAME${RESET}  ($FILESIZE bytes)"

# ── Step 2: Pick the K9 crystal size ─────────────────────────────────────────

echo ""
echo -e "${CYAN}Which K9 crystal are you using?${RESET}"
echo ""
echo "  1) K9 Rectangle 100×50×50 mm  — standard blank (~\$15–25)  [RECOMMENDED]"
echo "  2) K9 Rectangle, custom size"
echo ""
echo -n "  Choice [1]: "
read -r SIZE_CHOICE
SIZE_CHOICE="${SIZE_CHOICE:-1}"

if [ "$SIZE_CHOICE" = "2" ]; then
    echo -n "  Crystal XY dimension in mm (smaller side): "
    read -r CRYSTAL_MM
else
    CRYSTAL_MM=50
fi

# ── Step 3: Pick dot pitch ────────────────────────────────────────────────────

echo ""
echo -e "${CYAN}Dot pitch — how dense do you want the grid?${RESET}"
echo ""
echo "  1) 200 µm  — safe, easy to read back, lower density"
echo "  2) 100 µm  — recommended starting point               [DEFAULT]"
echo "  3)  75 µm  — higher density, needs good focus"
echo "  4)  50 µm  — aggressive, validate on 100µm first"
echo ""
echo -n "  Choice [2]: "
read -r PITCH_CHOICE
PITCH_CHOICE="${PITCH_CHOICE:-2}"

case "$PITCH_CHOICE" in
    1) PITCH_UM=200 ;;
    3) PITCH_UM=75  ;;
    4) PITCH_UM=50  ;;
    *) PITCH_UM=100 ;;
esac

# Use Python for all arithmetic — no bc dependency
PITCH_MM=$(python3 -c "print(f'{$PITCH_UM / 1000:.4f}')")
GRID=$(python3 -c "print(int($CRYSTAL_MM / ($PITCH_UM / 1000)))")

# ── Step 4: Pick layers ───────────────────────────────────────────────────────

echo ""
echo -e "${CYAN}How many Z layers?${RESET}"
echo -e "  (more layers = more capacity, but reading back needs per-layer focus)"
echo ""
echo "  1) 1 layer   — 2D flat, no Z-stack needed to read back    [EASIEST]"
echo "  2) 5 layers  — 2.5 mm depth, good balance                 [DEFAULT]"
echo "  3) 10 layers — 5 mm depth, higher capacity"
echo "  4) 20 layers — 10 mm depth"
echo "  5) Custom"
echo ""
echo -n "  Choice [2]: "
read -r LAYER_CHOICE
LAYER_CHOICE="${LAYER_CHOICE:-2}"

case "$LAYER_CHOICE" in
    1) LAYERS=1  ;;
    3) LAYERS=10 ;;
    4) LAYERS=20 ;;
    5) echo -n "  Number of layers: "; read -r LAYERS ;;
    *) LAYERS=5  ;;
esac

# ── Step 5: Pick ECC strength ─────────────────────────────────────────────────

echo ""
echo -e "${CYAN}Error correction strength?${RESET}"
echo ""
echo "  1) ECC=10  — light, max capacity"
echo "  2) ECC=20  — balanced (default, corrects ~8% errors)"
echo "  3) ECC=40  — strong (corrects ~16%, better for rough glass)"
echo "  4) Custom"
echo ""
echo -n "  Choice [2]: "
read -r ECC_CHOICE
ECC_CHOICE="${ECC_CHOICE:-2}"

case "$ECC_CHOICE" in
    1) ECC=10 ;;
    3) ECC=40 ;;
    4) echo -n "  ECC value (10–60): "; read -r ECC ;;
    *) ECC=20 ;;
esac

# ── Step 6: Show capacity and confirm ────────────────────────────────────────

echo ""
echo -e "${YELLOW}── Capacity check ──────────────────────────────${RESET}"
python3 encode_ssle_3d.py --capacity \
    --cols "$GRID" --rows "$GRID" \
    --layers "$LAYERS" \
    --xy-pitch "$PITCH_MM" \
    --ecc "$ECC" \
    --levels 4

echo ""
echo -e "  File to encode : ${BOLD}$FILENAME${RESET} ($FILESIZE bytes)"
echo ""

# Rough capacity check (Python)
USABLE_ROUGH=$(python3 -c "
grid=$GRID; layers=$LAYERS; ecc=$ECC; bpp=2
dc = grid - 2*(3+1)
raw_bytes = (dc * dc * layers * bpp) // 8
usable = int(raw_bytes * (235/255)) - 47
print(max(0, usable))
")

if [ "$FILESIZE" -gt "$USABLE_ROUGH" ]; then
    echo -e "${RED}  WARNING: File ($FILESIZE bytes) may be too large for this config (~${USABLE_ROUGH} bytes usable).${RESET}"
    echo "     Try more layers or a smaller file."
    echo ""
fi

echo -n "  Ready to encode? [Y/n]: "
read -r CONFIRM
CONFIRM="${CONFIRM:-Y}"
if [[ "$CONFIRM" =~ ^[Nn] ]]; then
    echo "Cancelled."
    exit 0
fi

# ── Step 7: Run encoder ───────────────────────────────────────────────────────

echo ""
echo -e "${YELLOW}── Encoding ─────────────────────────────────────${RESET}"
python3 encode_ssle_3d.py "$INPUT" \
    --cols "$GRID" --rows "$GRID" \
    --layers "$LAYERS" \
    --xy-pitch "$PITCH_MM" \
    --ecc "$ECC" \
    --levels 4

# Find the disc.json sidecar that was just written
BASENAME=$(python3 -c "import os; print(os.path.splitext('$INPUT')[0])")
DISC_JSON="${BASENAME}_voxel_disc.json"

# ── Step 8: Print xTool Studio instructions ───────────────────────────────────

ZDEPTH=$(python3 -c "print(f'{$LAYERS * 0.5:.1f}')")
GRIDMM=$(python3 -c "print(f'{$GRID * $PITCH_UM / 1000:.1f}')")

echo ""
echo -e "${GREEN}══════════════════════════════════════════════════${RESET}"
echo -e "${GREEN}  STLs ready. Here's exactly what to do next.${RESET}"
echo -e "${GREEN}══════════════════════════════════════════════════${RESET}"
echo ""
echo -e "${BOLD}Before you start:${RESET}"
echo "  • Swap to the inner engraving lens (ships in the box)"
echo "  • Setup guide: https://support.xtool.com/article/2708"
echo "  • Place K9 crystal flat and square in the machine"
echo ""
echo -e "${BOLD}In xTool Studio — 3 passes, do NOT move the crystal between them:${RESET}"
echo ""
echo -e "  ${CYAN}Pass 1 — Small dots (lowest power)${RESET}"
echo "    File   : ${BASENAME}_voxel_L1_small.stl"
echo "    Mode   : Inner Engraving (3D) → Dotting"
echo "    Size   : ${GRIDMM} × ${GRIDMM} × ${ZDEPTH} mm"
echo "    Power  : 50–60%   Speed: 500 mm/s   Dot Duration: 100–150 µs"
echo "    Check  : Clean dots under side-light. No cracks → continue."
echo ""
echo -e "  ${CYAN}Pass 2 — Medium dots${RESET}"
echo "    File   : ${BASENAME}_voxel_L2_medium.stl"
echo "    Mode   : Inner Engraving (3D) → Dotting"
echo "    Size   : ${GRIDMM} × ${GRIDMM} × ${ZDEPTH} mm"
echo "    Power  : 65–75%   Speed: 500 mm/s   Dot Duration: 100–150 µs"
echo ""
echo -e "  ${CYAN}Pass 3 — Large dots (full power)${RESET}"
echo "    File   : ${BASENAME}_voxel_L3_large.stl"
echo "    Mode   : Inner Engraving (3D) → Dotting"
echo "    Size   : ${GRIDMM} × ${GRIDMM} × ${ZDEPTH} mm"
echo "    Power  : 80–90%   Speed: 500 mm/s   Dot Duration: 150–200 µs"
echo ""
echo -e "${BOLD}To read it back later (keep the disc.json with the crystal):${RESET}"
if [ -f "$DISC_JSON" ]; then
    echo "  bash read_disc.sh --disc $DISC_JSON"
else
    echo "  python3 decode_ssle_3d.py --cols $GRID --rows $GRID --layers $LAYERS --ecc $ECC --levels 4"
fi
echo ""
echo -e "${YELLOW}Tip: start conservative on a fresh K9 — 55% / 150µs for Pass 1.${RESET}"
echo -e "${YELLOW}     Cloudy streaks = too much power. No dots = too little.${RESET}"
echo -e "${YELLOW}     Sidecar written to: ${DISC_JSON}${RESET}"
echo ""
