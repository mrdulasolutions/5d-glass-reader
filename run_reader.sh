#!/bin/bash
# run_reader.sh — Capture a glass disc and decode it back to the original file.
#
# Usage:
#   bash run_reader.sh                          # prompts for options
#   bash run_reader.sh --source xtool --file snapshot.png
#   bash run_reader.sh --source usb --disc myfile_5d_disc.json
#   bash run_reader.sh --source pi --cols 200 --rows 200 --ecc 20 --levels 4
#   bash run_reader.sh --source file --file my_scan.jpg --disc myfile_5d_disc.json

set -e

BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
CYAN="\033[0;36m"
RED="\033[0;31m"
RESET="\033[0m"

SOURCE=""
FILE_ARG=""
DISC_JSON=""
COLS=200
ROWS=200
ECC=20
LEVELS=4
THRESHOLD=80
OUTPUT_DIR="output"
CAPTURE_OUT="raw_scattering/capture.png"

print_usage() {
    echo "Usage: bash run_reader.sh [options]"
    echo ""
    echo "  --source   xtool|usb|pi|file  (default: prompt)"
    echo "  --file     path to snapshot/image  (required for xtool/file sources)"
    echo "  --disc     path to disc.json sidecar (auto-sets cols/rows/ecc/levels)"
    echo "  --cols     grid columns  (default: 200)"
    echo "  --rows     grid rows     (default: 200)"
    echo "  --ecc      RS ECC symbols (default: 20)"
    echo "  --levels   2 or 4        (default: 4, True 5D)"
    echo "  --threshold fiducial detection threshold (default: 80)"
    echo "  --output   output directory (default: output)"
}

# ── Parse arguments ───────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case "$1" in
        --source)    SOURCE="$2";    shift 2 ;;
        --file)      FILE_ARG="$2";  shift 2 ;;
        --disc)      DISC_JSON="$2"; shift 2 ;;
        --cols)      COLS="$2";      shift 2 ;;
        --rows)      ROWS="$2";      shift 2 ;;
        --ecc)       ECC="$2";       shift 2 ;;
        --levels)    LEVELS="$2";    shift 2 ;;
        --threshold) THRESHOLD="$2"; shift 2 ;;
        --output)    OUTPUT_DIR="$2";shift 2 ;;
        --help|-h)   print_usage; exit 0 ;;
        *)
            echo -e "${RED}Unknown option: $1${RESET}"
            print_usage
            exit 1
            ;;
    esac
done

# ── Load disc.json if provided ────────────────────────────────────────────────

if [ -n "$DISC_JSON" ]; then
    if [ ! -f "$DISC_JSON" ]; then
        echo -e "${RED}ERROR: disc.json not found: $DISC_JSON${RESET}"
        exit 1
    fi
    echo -e "${CYAN}Loading parameters from $DISC_JSON...${RESET}"
    COLS=$(python3   -c "import json; d=json.load(open('$DISC_JSON')); print(d.get('cols', $COLS))")
    ROWS=$(python3   -c "import json; d=json.load(open('$DISC_JSON')); print(d.get('rows', $ROWS))")
    ECC=$(python3    -c "import json; d=json.load(open('$DISC_JSON')); print(d.get('ecc', $ECC))")
    LEVELS=$(python3 -c "import json; d=json.load(open('$DISC_JSON')); print(d.get('levels', $LEVELS))")
    echo "  cols=$COLS  rows=$ROWS  ecc=$ECC  levels=$LEVELS"
fi

# ── Prompt for source if not given ───────────────────────────────────────────

if [ -z "$SOURCE" ]; then
    echo ""
    echo -e "${BOLD}How are you capturing the disc?${RESET}"
    echo ""
    echo "  1) xtool  — xTool Studio snapshot (FASTEST, same machine)  [RECOMMENDED]"
    echo "  2) usb    — USB digital microscope / webcam"
    echo "  3) pi     — Raspberry Pi HQ Camera (most accurate)"
    echo "  4) file   — Use an existing image file"
    echo ""
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

# ── Source-specific prompts ───────────────────────────────────────────────────

if [ "$SOURCE" = "xtool" ] && [ -z "$FILE_ARG" ]; then
    echo ""
    echo -e "${CYAN}xTool snapshot path:${RESET}"
    echo "  (In xTool Studio: Camera icon → Snapshot → Save image. Drag the file here.)"
    echo -n "  File path: "
    read -r FILE_ARG
    FILE_ARG="${FILE_ARG%\"}"
    FILE_ARG="${FILE_ARG#\"}"
    FILE_ARG="${FILE_ARG% }"
fi

if [ "$SOURCE" = "file" ] && [ -z "$FILE_ARG" ]; then
    echo ""
    echo -n "  Image path: "
    read -r FILE_ARG
    FILE_ARG="${FILE_ARG%\"}"
    FILE_ARG="${FILE_ARG#\"}"
fi

# ── Validate ──────────────────────────────────────────────────────────────────

if [ "$SOURCE" = "xtool" ] || [ "$SOURCE" = "file" ]; then
    if [ -z "$FILE_ARG" ] || [ ! -f "$FILE_ARG" ]; then
        echo -e "${RED}ERROR: File not found: $FILE_ARG${RESET}"
        exit 1
    fi
fi

# ── Setup directories ─────────────────────────────────────────────────────────

mkdir -p raw_scattering "$OUTPUT_DIR"

# ── Step 1: Capture ───────────────────────────────────────────────────────────

echo ""
echo -e "${YELLOW}── Step 1: Capture ───────────────────────────────${RESET}"

CAPTURE_ARGS="--source $SOURCE --output $CAPTURE_OUT"
[ -n "$FILE_ARG" ] && CAPTURE_ARGS="$CAPTURE_ARGS --file \"$FILE_ARG\""

eval python3 capture_scattering.py $CAPTURE_ARGS

if [ ! -f "$CAPTURE_OUT" ]; then
    echo -e "${RED}ERROR: Capture failed — $CAPTURE_OUT not found${RESET}"
    exit 1
fi

# ── Step 2: Decode ────────────────────────────────────────────────────────────

echo ""
echo -e "${YELLOW}── Step 2: Decode ────────────────────────────────${RESET}"

DECODE_ARGS="$CAPTURE_OUT --output $OUTPUT_DIR --cols $COLS --rows $ROWS --ecc $ECC --levels $LEVELS --threshold $THRESHOLD"
[ -n "$DISC_JSON" ] && DECODE_ARGS="$DECODE_ARGS --disc $DISC_JSON"

python3 decode_ssle.py $DECODE_ARGS

echo ""
echo -e "${GREEN}Done. Recovered file(s) in: $OUTPUT_DIR/${RESET}"
