#!/bin/bash
# read_disc.sh — Read a glass disc back using its disc.json sidecar.
#
# The disc.json file is written automatically by make_stl.sh / encode_ssle.py /
# encode_ssle_3d.py alongside the STL or PNG output. Keep it with the crystal.
#
# Supports both 2D (single-layer PNG) and 3D (multi-layer) discs.
#
# Usage:
#   bash read_disc.sh                               # interactive — prompts for everything
#   bash read_disc.sh --disc myfile_voxel_disc.json
#   bash read_disc.sh --disc myfile_5d_disc.json --source xtool --file snapshot.png

set -e

BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
CYAN="\033[0;36m"
RED="\033[0;31m"
RESET="\033[0m"

DISC_JSON=""
SOURCE=""
FILE_ARG=""
OUTPUT_DIR="output"
THRESHOLD=80

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║   5D Glass Eternal Drive — Disc Reader       ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════════════════════╝${RESET}"
echo ""

# ── Parse arguments ───────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case "$1" in
        --disc)      DISC_JSON="$2"; shift 2 ;;
        --source)    SOURCE="$2";    shift 2 ;;
        --file)      FILE_ARG="$2";  shift 2 ;;
        --output)    OUTPUT_DIR="$2";shift 2 ;;
        --threshold) THRESHOLD="$2"; shift 2 ;;
        --help|-h)
            echo "Usage: bash read_disc.sh [--disc disc.json] [--source xtool|usb|pi|file] [--file path]"
            exit 0 ;;
        *)
            echo -e "${RED}Unknown option: $1${RESET}"
            exit 1 ;;
    esac
done

# ── Find or prompt for disc.json ─────────────────────────────────────────────

if [ -z "$DISC_JSON" ]; then
    # Look for any disc.json in current dir
    FOUND=$(ls *_disc.json 2>/dev/null | head -1 || true)
    if [ -n "$FOUND" ]; then
        echo -e "${CYAN}Found sidecar: $FOUND${RESET}"
        echo -n "  Use this disc.json? [Y/n]: "
        read -r USE_FOUND
        USE_FOUND="${USE_FOUND:-Y}"
        if [[ ! "$USE_FOUND" =~ ^[Nn] ]]; then
            DISC_JSON="$FOUND"
        fi
    fi
fi

if [ -z "$DISC_JSON" ]; then
    echo -e "${CYAN}Path to disc.json sidecar (drag-drop or type):${RESET}"
    echo -n "  File: "
    read -r DISC_JSON
    DISC_JSON="${DISC_JSON%\"}"
    DISC_JSON="${DISC_JSON#\"}"
    DISC_JSON="${DISC_JSON% }"
fi

if [ ! -f "$DISC_JSON" ]; then
    echo -e "${RED}ERROR: disc.json not found: $DISC_JSON${RESET}"
    echo "  Each disc.json is written when you encode — keep it with the crystal."
    exit 1
fi

# ── Parse disc.json ───────────────────────────────────────────────────────────

FORMAT=$(python3  -c "import json; d=json.load(open('$DISC_JSON')); print(d.get('format','2D'))")
COLS=$(python3    -c "import json; d=json.load(open('$DISC_JSON')); print(d.get('cols', 200))")
ROWS=$(python3    -c "import json; d=json.load(open('$DISC_JSON')); print(d.get('rows', 200))")
ECC=$(python3     -c "import json; d=json.load(open('$DISC_JSON')); print(d.get('ecc', 20))")
LEVELS=$(python3  -c "import json; d=json.load(open('$DISC_JSON')); print(d.get('levels', 4))")
SRC_FILE=$(python3 -c "import json; d=json.load(open('$DISC_JSON')); print(d.get('source_file',''))")
LAYERS=$(python3  -c "import json; d=json.load(open('$DISC_JSON')); print(d.get('layers', 1))")
LAYERS_DIR=$(python3 -c "import json; d=json.load(open('$DISC_JSON')); print(d.get('layer_pngs_dir') or '')")

echo ""
echo -e "${YELLOW}── Disc Parameters ───────────────────────────────${RESET}"
echo "  Format     : $FORMAT"
echo "  Grid       : ${COLS}×${ROWS}"
[ "$FORMAT" = "3D" ] && echo "  Layers     : $LAYERS"
echo "  ECC        : $ECC"
echo "  Levels     : $LEVELS"
echo "  Encoded    : $SRC_FILE"
echo ""

mkdir -p raw_scattering "$OUTPUT_DIR"

# ── Capture ───────────────────────────────────────────────────────────────────

if [ "$FORMAT" = "3D" ]; then
    echo -e "${BOLD}3D disc — you need one capture per Z layer.${RESET}"
    echo "  Use a motorized Z stage or manually refocus between layers."
    echo "  Each capture: adjust focus → run capture → save as layer_NN.png"
    echo ""
    echo -n "  Directory of per-layer PNGs [raw_scattering/layers]: "
    read -r LAYERS_DIR_INPUT
    LAYERS_DIR_INPUT="${LAYERS_DIR_INPUT:-raw_scattering/layers}"
    [ -n "$LAYERS_DIR_INPUT" ] && LAYERS_DIR="$LAYERS_DIR_INPUT"

    if [ ! -d "$LAYERS_DIR" ] || [ -z "$(ls "$LAYERS_DIR"/*.png 2>/dev/null)" ]; then
        echo -e "${YELLOW}No PNGs found in $LAYERS_DIR${RESET}"
        echo "  Capture each layer:"
        echo "    python3 capture_scattering.py --source xtool --file snapshot_L00.png --output $LAYERS_DIR/layer_00.png"
        echo "    ... (repeat for each Z depth)"
        exit 1
    fi
else
    # 2D: single capture
    if [ -z "$SOURCE" ]; then
        echo -e "${CYAN}Capture source:${RESET}"
        echo "  1) xtool  — xTool Studio snapshot  [RECOMMENDED]"
        echo "  2) usb    — USB microscope"
        echo "  3) pi     — Pi HQ Camera"
        echo "  4) file   — existing image"
        echo -n "  Choice [1]: "
        read -r SRC_CHOICE
        SRC_CHOICE="${SRC_CHOICE:-1}"
        case "$SRC_CHOICE" in
            2) SOURCE="usb" ;;
            3) SOURCE="pi"  ;;
            4) SOURCE="file" ;;
            *) SOURCE="xtool" ;;
        esac
    fi

    if [ "$SOURCE" = "xtool" ] && [ -z "$FILE_ARG" ]; then
        echo ""
        echo -e "${CYAN}xTool snapshot path:${RESET}"
        echo "  (xTool Studio → Camera icon → Snapshot → save file. Drag here.)"
        echo -n "  File: "
        read -r FILE_ARG
        FILE_ARG="${FILE_ARG%\"}"
        FILE_ARG="${FILE_ARG#\"}"
        FILE_ARG="${FILE_ARG% }"
    fi

    if [ "$SOURCE" = "file" ] && [ -z "$FILE_ARG" ]; then
        echo -n "  Image path: "
        read -r FILE_ARG
        FILE_ARG="${FILE_ARG%\"}"
        FILE_ARG="${FILE_ARG#\"}"
    fi

    CAPTURE_OUT="raw_scattering/capture.png"
    CAPTURE_ARGS="--source $SOURCE --output $CAPTURE_OUT"
    [ -n "$FILE_ARG" ] && CAPTURE_ARGS="$CAPTURE_ARGS --file \"$FILE_ARG\""

    echo ""
    echo -e "${YELLOW}── Capturing ─────────────────────────────────────${RESET}"
    eval python3 capture_scattering.py $CAPTURE_ARGS

    if [ ! -f "$CAPTURE_OUT" ]; then
        echo -e "${RED}ERROR: Capture failed.${RESET}"
        exit 1
    fi
fi

# ── Decode ────────────────────────────────────────────────────────────────────

echo ""
echo -e "${YELLOW}── Decoding ──────────────────────────────────────${RESET}"

if [ "$FORMAT" = "3D" ]; then
    python3 decode_ssle_3d.py "$LAYERS_DIR" \
        --disc "$DISC_JSON" \
        --output "$OUTPUT_DIR" \
        --threshold "$THRESHOLD"
else
    python3 decode_ssle.py "$CAPTURE_OUT" \
        --disc "$DISC_JSON" \
        --output "$OUTPUT_DIR" \
        --threshold "$THRESHOLD"
fi

echo ""
echo -e "${GREEN}Done. Recovered file(s) in: $OUTPUT_DIR/${RESET}"
