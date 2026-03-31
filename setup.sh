#!/bin/bash
# setup.sh — One-time install for 5D Glass Eternal Drive
# Works on: Raspberry Pi 5 (full stack) · macOS · Windows (WSL)
# Run once after: git clone https://github.com/mrdulasolutions/5d-glass-reader.git

set -e

BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
CYAN="\033[0;36m"
DIM="\033[2m"
RESET="\033[0m"

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║                                                          ║${RESET}"
echo -e "${BOLD}║   5D Glass Eternal Drive — Setup                        ║${RESET}"
echo -e "${BOLD}║   mrdulasolutions/5d-glass-reader                       ║${RESET}"
echo -e "${BOLD}║                                                          ║${RESET}"
echo -e "${BOLD}║   Store data permanently inside glass.                   ║${RESET}"
echo -e "${BOLD}║   No lab. No gatekeepers. Just a UV laser.               ║${RESET}"
echo -e "${BOLD}║                                                          ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${RESET}"
echo ""

# ── Detect platform ───────────────────────────────────────────────────────────

PLATFORM="unknown"
IS_PI=false

if [ -f /proc/device-tree/model ] && grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    IS_PI=true
    PI_MODEL=$(tr -d '\0' < /proc/device-tree/model)
    PLATFORM="Raspberry Pi ($PI_MODEL)"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    PLATFORM="macOS"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    PLATFORM="Linux"
elif [[ "$OSTYPE" == "msys"* ]] || [[ "$OSTYPE" == "cygwin"* ]]; then
    PLATFORM="Windows (WSL)"
fi

echo -e "  ${DIM}Platform : $PLATFORM${RESET}"
echo -e "  ${DIM}Python   : $(python3 --version 2>&1)${RESET}"
echo ""

# ── Step 1: Create runtime directories ───────────────────────────────────────

echo -e "${CYAN}[1/4] Creating runtime directories...${RESET}"
mkdir -p raw_scattering raw_scattering/layers output
touch raw_scattering/.gitkeep raw_scattering/layers/.gitkeep output/.gitkeep
echo -e "      ${DIM}raw_scattering/  output/  raw_scattering/layers/${RESET}"

# ── Step 2: Make scripts executable ──────────────────────────────────────────

echo -e "${CYAN}[2/4] Making scripts executable...${RESET}"
chmod +x run_reader.sh setup.sh make_stl.sh 2>/dev/null || true

# ── Step 3: Install Python dependencies ──────────────────────────────────────

echo -e "${CYAN}[3/4] Installing Python dependencies...${RESET}"

if $IS_PI; then
    # Pi: install all deps including picamera2 and RPi.GPIO via apt first
    echo -e "      ${DIM}Raspberry Pi detected — installing system packages first${RESET}"
    sudo apt-get update -qq
    sudo apt-get install -y -qq python3-picamera2 python3-libcamera python3-opencv python3-numpy python3-pip
    pip3 install --break-system-packages reedsolo 2>/dev/null || pip3 install reedsolo
    # RPi.GPIO
    pip3 install --break-system-packages RPi.GPIO 2>/dev/null || pip3 install RPi.GPIO
else
    # Mac/Linux: install what we can (picamera2 and RPi.GPIO are Pi-only, will be skipped)
    pip3 install reedsolo numpy opencv-python 2>&1 | grep -E "^(Successfully|Already|ERROR)" || true
    echo -e "      ${DIM}Note: picamera2 and RPi.GPIO are Pi-only — skipped on this platform${RESET}"
fi

# ── Step 4: Verify ────────────────────────────────────────────────────────────

echo -e "${CYAN}[4/4] Verifying install...${RESET}"

FAIL=false
for pkg in reedsolo numpy cv2; do
    if python3 -c "import $pkg" 2>/dev/null; then
        echo -e "      ${DIM}✓ $pkg${RESET}"
    else
        echo -e "      ${YELLOW}✗ $pkg — not found (install manually: pip3 install $pkg)${RESET}"
        FAIL=true
    fi
done

if $IS_PI; then
    for pkg in picamera2 RPi; do
        if python3 -c "import $pkg" 2>/dev/null; then
            echo -e "      ${DIM}✓ $pkg${RESET}"
        else
            echo -e "      ${YELLOW}✗ $pkg — Pi camera features won't work${RESET}"
        fi
    done
fi

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
if $FAIL; then
    echo -e "${YELLOW}  Setup completed with warnings. Fix missing packages above, then re-run.${RESET}"
else
    echo -e "${GREEN}  ✅  Setup complete.${RESET}"
fi

echo ""
echo -e "${BOLD}  What to do next:${RESET}"
echo ""
echo -e "  ${GREEN}1. Verify software pipeline (no hardware needed):${RESET}"
echo      "     python3 test_pipeline.py"
echo ""
echo -e "  ${GREEN}2. Encode a file to STL for xTool Studio:${RESET}"
echo      "     bash make_stl.sh myfile.txt"
echo ""
echo -e "  ${GREEN}3. Download xTool Studio (free):${RESET}"
echo      "     https://www.xtool.com/pages/software"
echo -e "     ${DIM}Windows · macOS-Intel · macOS-M  —  v1.6.6${RESET}"
echo ""
echo -e "  ${GREEN}4. Required reading before first engrave:${RESET}"
echo -e "     ${DIM}Course 279 — Getting Started:  support.xtool.com/academy/course?id=279${RESET}"
echo -e "     ${DIM}Course 280 — Software & Materials:  ...course?id=280${RESET}"
echo -e "     ${DIM}Course 281 — Inner Engraving Best Practices:  ...course?id=281${RESET}"
echo ""
if $IS_PI; then
    echo -e "  ${GREEN}5. Test stage control (simulation mode):${RESET}"
    echo      "     python3 stage_control.py --sim --x 10 --y 10"
    echo ""
    echo -e "  ${GREEN}6. Run the reader (after engraving):${RESET}"
    echo      "     ./run_reader.sh"
    echo ""
fi
echo -e "  ${DIM}Docs: github.com/mrdulasolutions/5d-glass-reader${RESET}"
echo ""
