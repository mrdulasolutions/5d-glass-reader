#!/bin/bash
# setup.sh — Complete setup guide for 5D Glass Eternal Drive
# Covers: software install · xTool Studio · machine connection · lens swap ·
#         loading STL · engraving · snapshot capture · decode
#
# Run once after: git clone https://github.com/mrdulasolutions/EternalDrive-IndieHack.git
# Then follow the interactive walkthrough.

set -e

BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
CYAN="\033[0;36m"
RED="\033[0;31m"
DIM="\033[2m"
RESET="\033[0m"

pause() {
    echo ""
    echo -n "  Press Enter to continue..."
    read -r
    echo ""
}

section() {
    echo ""
    echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo -e "${BOLD}  $1${RESET}"
    echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo ""
}

step() {
    echo -e "  ${GREEN}▶${RESET} $1"
}

note() {
    echo -e "  ${YELLOW}ℹ${RESET}  $1"
}

warn() {
    echo -e "  ${RED}⚠${RESET}  $1"
}

ok() {
    echo -e "  ${GREEN}✓${RESET} $1"
}

# ── Banner ────────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║                                                          ║${RESET}"
echo -e "${BOLD}║   5D Glass Eternal Drive — Full Setup Guide              ║${RESET}"
echo -e "${BOLD}║   mrdulasolutions/EternalDrive-IndieHack                       ║${RESET}"
echo -e "${BOLD}║                                                          ║${RESET}"
echo -e "${BOLD}║   Store data permanently inside glass.                   ║${RESET}"
echo -e "${BOLD}║   No lab. No gatekeepers. Just a UV laser.               ║${RESET}"
echo -e "${BOLD}║                                                          ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${RESET}"
echo ""

# ── Detect platform ───────────────────────────────────────────────────────────

IS_PI=false
if [ -f /proc/device-tree/model ] && grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    IS_PI=true
    PI_MODEL=$(tr -d '\0' < /proc/device-tree/model)
    echo -e "  ${DIM}Platform : Raspberry Pi — $PI_MODEL${RESET}"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo -e "  ${DIM}Platform : macOS${RESET}"
else
    echo -e "  ${DIM}Platform : Linux / WSL${RESET}"
fi
echo -e "  ${DIM}Python   : $(python3 --version 2>&1)${RESET}"
echo ""

echo -e "  This script will walk you through:"
echo -e "  ${DIM}  1. Software install & verification${RESET}"
echo -e "  ${DIM}  2. xTool Studio download & machine connection${RESET}"
echo -e "  ${DIM}  3. Inner engraving lens swap${RESET}"
echo -e "  ${DIM}  4. Encoding a file → STL${RESET}"
echo -e "  ${DIM}  5. Loading STL into xTool Studio & engraving${RESET}"
echo -e "  ${DIM}  6. Taking a snapshot to read the disc back${RESET}"
echo -e "  ${DIM}  7. Decoding — recovering your file from glass${RESET}"

pause

# ══════════════════════════════════════════════════════════════════════════════
# PART 1 — SOFTWARE INSTALL
# ══════════════════════════════════════════════════════════════════════════════

section "Part 1 of 7 — Software Install"

step "Creating runtime directories..."
mkdir -p raw_scattering raw_scattering/layers output
touch raw_scattering/.gitkeep raw_scattering/layers/.gitkeep output/.gitkeep
ok "raw_scattering/  output/  raw_scattering/layers/"

step "Making scripts executable..."
chmod +x run_reader.sh setup.sh make_stl.sh 2>/dev/null || true
ok "run_reader.sh  make_stl.sh"

step "Installing Python dependencies..."
if $IS_PI; then
    note "Raspberry Pi — installing system packages first (needs sudo)"
    sudo apt-get update -qq
    sudo apt-get install -y -qq python3-picamera2 python3-libcamera python3-opencv python3-numpy python3-pip
    pip3 install --break-system-packages reedsolo 2>/dev/null || pip3 install reedsolo
    pip3 install --break-system-packages RPi.GPIO 2>/dev/null || pip3 install RPi.GPIO
else
    pip3 install reedsolo numpy opencv-python 2>&1 | grep -E "^(Successfully|Already|ERROR)" || true
    note "picamera2 and RPi.GPIO are Pi-only — skipped on this platform"
fi

step "Verifying install..."
FAIL=false
for pkg in reedsolo numpy cv2; do
    if python3 -c "import $pkg" 2>/dev/null; then
        ok "$pkg"
    else
        warn "$pkg not found — install manually: pip3 install $pkg"
        FAIL=true
    fi
done

if $FAIL; then
    warn "Fix missing packages above before continuing."
    exit 1
fi

step "Running software pipeline test (no hardware needed)..."
echo ""
python3 test_pipeline.py
echo ""
ok "Pipeline test passed — encode → decode round-trip works."

pause

# ══════════════════════════════════════════════════════════════════════════════
# PART 2 — xTool STUDIO DOWNLOAD & MACHINE CONNECTION
# ══════════════════════════════════════════════════════════════════════════════

section "Part 2 of 7 — xTool Studio: Download & Connect"

echo -e "  xTool Studio is the free software that controls the F2 Ultra."
echo -e "  It handles the inner engraving, camera snapshots, and job setup."
echo ""
step "Download xTool Studio (free):"
echo ""
echo -e "     ${BOLD}https://www.xtool.com/pages/software${RESET}"
echo ""
echo -e "     Windows      — xTool Studio for Windows"
echo -e "     macOS Intel  — xTool Studio macOS-Intel"
echo -e "     macOS M1/M2+ — xTool Studio macOS-M"
echo -e "     ${DIM}Current version: v1.6.6  (March 2026)${RESET}"
echo ""
note "Install it and open it before continuing."
pause

step "Connect the F2 Ultra to your computer:"
echo ""
echo -e "     1. Power on the F2 Ultra (switch on the back)"
echo -e "     2. Connect the ${BOLD}USB-C cable${RESET} from the machine to your computer"
echo -e "        ${DIM}(the USB-C port is on the left side of the machine)${RESET}"
echo -e "     3. In xTool Studio: look for the machine icon in the top-left"
echo -e "        It should show ${BOLD}\"F2 Ultra UV\"${RESET} — click Connect"
echo ""
note "If it doesn't appear: check USB cable, try a different port, restart Studio."
note "WiFi connection also works — F2 Ultra broadcasts its own hotspot."
echo ""
echo -e "     ${BOLD}WiFi option:${RESET}"
echo -e "     1. On the machine touchscreen: Settings → Network → AP Mode"
echo -e "     2. Connect your laptop to the F2 Ultra WiFi network"
echo -e "     3. xTool Studio will auto-detect it"
echo ""
step "Complete the required xTool Academy courses (takes ~30 min total):"
echo ""
echo -e "     ${CYAN}Course 279${RESET} — Getting Started with F2 Ultra UV"
echo -e "     ${DIM}https://support.xtool.com/academy/course?id=279${RESET}"
echo ""
echo -e "     ${CYAN}Course 280${RESET} — Essentials: Software & Materials"
echo -e "     ${DIM}https://support.xtool.com/academy/course?id=280${RESET}"
echo ""
echo -e "     ${CYAN}Course 281${RESET} — Inner Engraving: Skills and Best Practices"
echo -e "     ${DIM}https://support.xtool.com/academy/course?id=281${RESET}"
echo ""
warn "Do NOT skip 281 — inner engraving has specific safety steps."

pause

# ══════════════════════════════════════════════════════════════════════════════
# PART 3 — INNER ENGRAVING LENS SWAP
# ══════════════════════════════════════════════════════════════════════════════

section "Part 3 of 7 — Inner Engraving Lens Swap"

echo -e "  The F2 Ultra ships with two lenses: the surface lens (installed)"
echo -e "  and the inner engraving lens (in the accessory box)."
echo -e "  You must swap to the inner lens before engraving inside glass."
echo ""
warn "POWER OFF the machine before swapping lenses."
echo ""
step "How to swap the lens:"
echo ""
echo -e "     Full guide with photos:"
echo -e "     ${BOLD}https://support.xtool.com/article/2708${RESET}"
echo ""
echo -e "     Quick steps:"
echo -e "     1. Power off the F2 Ultra"
echo -e "     2. Locate the lens module on the laser head (black rectangular module)"
echo -e "     3. Unscrew the two thumbscrews holding the surface lens"
echo -e "     4. Carefully remove the surface lens module"
echo -e "     5. Insert the ${BOLD}inner engraving lens${RESET} — it only fits one way"
echo -e "     6. Tighten the thumbscrews — snug but not forced"
echo -e "     7. Power on"
echo ""
echo -e "     In xTool Studio — tell it which lens is installed:"
echo -e "     ${DIM}Machine Settings → Lens → Inner Engraving Lens${RESET}"
echo ""
note "The inner lens has a longer focal length — the Z height will be different."
note "Always run xTool's auto-focus after swapping."

pause

# ══════════════════════════════════════════════════════════════════════════════
# PART 4 — ENCODE A FILE TO STL
# ══════════════════════════════════════════════════════════════════════════════

section "Part 4 of 7 — Encode a File to STL"

echo -e "  Now encode your file into the 3D voxel STLs that xTool Studio imports."
echo ""
echo -e "  The encoder outputs ${BOLD}3 STL files${RESET} (one per dot size level)."
echo -e "  You'll run 3 engraving passes — one per file."
echo ""

echo -n "  Do you want to encode a file now? [Y/n]: "
read -r DO_ENCODE
DO_ENCODE="${DO_ENCODE:-Y}"

if [[ "$DO_ENCODE" =~ ^[Yy] ]]; then
    echo ""
    step "Launching interactive encoder..."
    echo ""
    bash make_stl.sh
else
    echo ""
    note "Skipped. Run this any time to encode a file:"
    echo -e "     ${BOLD}bash make_stl.sh myfile.txt${RESET}"
fi

pause

# ══════════════════════════════════════════════════════════════════════════════
# PART 5 — LOADING STL INTO xTool STUDIO & ENGRAVING
# ══════════════════════════════════════════════════════════════════════════════

section "Part 5 of 7 — Load STL into xTool Studio & Engrave"

echo -e "  You have 3 STL files. You'll import and engrave them one at a time."
echo -e "  ${BOLD}Do not move the crystal between passes.${RESET}"
echo ""

step "Place the K9 crystal in the machine:"
echo ""
echo -e "     1. Open the lid of the F2 Ultra"
echo -e "     2. Place the K9 crystal flat on the honeycomb bed"
echo -e "     3. Position it centered under the laser head"
echo -e "     4. Close the lid"
echo ""

step "Run auto-focus:"
echo ""
echo -e "     In xTool Studio:"
echo -e "     1. Click the ${BOLD}Auto Focus${RESET} button (target icon, top toolbar)"
echo -e "     2. The laser head will lower and probe the crystal surface"
echo -e "     3. Wait for it to complete — it sets Z=0 at the crystal top"
echo ""
note "Inner engraving Z depth is measured down from the surface."
note "We engrave at 1mm below surface by default."
echo ""

step "Load Pass 1 — Small dots (lowest power):"
echo ""
echo -e "     1. In xTool Studio: ${BOLD}File → New Project${RESET}"
echo -e "     2. Click ${BOLD}Import${RESET} (or drag-drop) your ${BOLD}_L1_small.stl${RESET} file"
echo -e "     3. The model appears in the workspace as a 3D dot cloud"
echo ""
echo -e "     ${BOLD}Set the physical size:${RESET}"
echo -e "     4. Click the model → in the right panel set:"
echo -e "        ${DIM}Width  = (your grid mm — shown in make_stl.sh output)${RESET}"
echo -e "        ${DIM}Height = same value${RESET}"
echo -e "        ${DIM}Depth  = Z depth shown in make_stl.sh output${RESET}"
echo -e "        ${YELLOW}⚠  Lock aspect ratio OFF before setting size${RESET}"
echo ""
echo -e "     ${BOLD}Set engraving parameters:${RESET}"
echo -e "     5. Mode      → ${BOLD}Inner Engraving (3D)${RESET}"
echo -e "     6. Sub-mode  → ${BOLD}Dotting${RESET}  (not Scanning)"
echo -e "     7. Power     → ${BOLD}50–60%${RESET}"
echo -e "     8. Speed     → ${BOLD}500 mm/s${RESET}"
echo -e "     9. Dot Time  → ${BOLD}100–150 µs${RESET}"
echo -e "    10. Z offset  → ${BOLD}1.0 mm${RESET}  (depth below surface)"
echo ""
echo -e "     ${BOLD}Engrave:${RESET}"
echo -e "    11. Click ${BOLD}Frame${RESET} first — the laser traces the boundary without firing"
echo -e "        Confirm it fits within the crystal area"
echo -e "    12. Click ${BOLD}Start${RESET}"
echo -e "    13. Watch the first few dots. They should appear as ${BOLD}bright white${RESET}"
echo -e "        scattering points visible inside the glass."
echo ""
warn "Cloudy streaks or cracks = power too high. Stop, reduce by 5%, retry."
warn "No visible dots = power too low. Stop, increase by 5%, retry."
echo ""
echo -n "  Press Enter when Pass 1 is complete..."
read -r
echo ""

step "Load Pass 2 — Medium dots:"
echo ""
echo -e "     1. ${BOLD}File → New Project${RESET}  (start fresh — do NOT move the crystal)"
echo -e "     2. Import ${BOLD}_L2_medium.stl${RESET}"
echo -e "     3. Set the same physical size as Pass 1"
echo -e "     4. Power → ${BOLD}65–75%${RESET}   (everything else same as Pass 1)"
echo -e "     5. Engrave"
echo ""
echo -n "  Press Enter when Pass 2 is complete..."
read -r
echo ""

step "Load Pass 3 — Large dots (full power):"
echo ""
echo -e "     1. ${BOLD}File → New Project${RESET}"
echo -e "     2. Import ${BOLD}_L3_large.stl${RESET}"
echo -e "     3. Set the same physical size"
echo -e "     4. Power → ${BOLD}80–90%${RESET}   Dot Time → ${BOLD}150–200 µs${RESET}"
echo -e "     5. Engrave"
echo ""
echo -n "  Press Enter when Pass 3 is complete..."
read -r

pause

# ══════════════════════════════════════════════════════════════════════════════
# PART 6 — SNAPSHOT: READING THE DISC WITH THE F2 ULTRA CAMERA
# ══════════════════════════════════════════════════════════════════════════════

section "Part 6 of 7 — Snapshot: Read with the F2 Ultra Camera"

echo -e "  The F2 Ultra's dual 48MP cameras can image the engraved dot pattern."
echo -e "  You don't need any extra hardware for a basic read."
echo ""

step "Set up raking light for the snapshot:"
echo ""
echo -e "     The dots are only visible under ${BOLD}side (raking) illumination${RESET}."
echo -e "     Overhead light makes them invisible."
echo ""
echo -e "     1. Keep the crystal in the machine (do not move it)"
echo -e "     2. Open the lid slightly"
echo -e "     3. Shine a ${BOLD}flashlight or phone torch${RESET} at a ${BOLD}low angle (~20°)${RESET}"
echo -e "        along the surface of the crystal"
echo -e "     4. You should see the dots glow ${BOLD}bright white${RESET} inside the glass"
echo -e "     5. Rotate the light angle until the dots are clearest"
echo ""
note "The dots won't all be visible at once — that's fine, the camera captures the full grid."
echo ""

step "Take the snapshot in xTool Studio:"
echo ""
echo -e "     1. In xTool Studio, click the ${BOLD}Camera icon${RESET} (top-right of workspace)"
echo -e "     2. Click ${BOLD}Snapshot${RESET} or ${BOLD}Take Photo${RESET}"
echo -e "     3. Wait for the camera to capture — it saves a full-resolution image"
echo -e "     4. Note the saved file path (usually your Documents or Desktop)"
echo -e "        ${DIM}Typical path: ~/Documents/xTool Studio/snapshot_YYYYMMDD_HHMMSS.jpg${RESET}"
echo ""
note "If the dots look faint in the snapshot, try: raise side-light angle, darken the room."
note "Increase contrast in the camera preview if xTool Studio offers it."
echo ""

step "Copy the snapshot into this project:"
echo ""
echo -e "     Run this (replace with your actual snapshot path):"
echo ""
echo -e "     ${BOLD}python3 capture_scattering.py --source xtool --file ~/path/to/snapshot.jpg${RESET}"
echo ""
echo -e "     This copies it to ${BOLD}raw_scattering/capture.png${RESET} ready for the decoder."
echo ""
echo -n "  Press Enter when you have the snapshot copied to raw_scattering/..."
read -r

pause

# ══════════════════════════════════════════════════════════════════════════════
# PART 7 — DECODE: RECOVER YOUR FILE FROM GLASS
# ══════════════════════════════════════════════════════════════════════════════

section "Part 7 of 7 — Decode: Recover Your File from Glass"

echo -e "  The decoder reads the snapshot, finds the fiducial markers,"
echo -e "  corrects perspective, classifies each dot's gray level,"
echo -e "  and runs Reed-Solomon error correction to recover the original file."
echo ""

# Try to pull grid params from any recent STL output
COLS=500
ROWS=500
LAYERS=5
ECC=20

step "Run the decoder:"
echo ""
echo -e "     ${BOLD}For 3D (multi-layer STL):${RESET}"
echo -e "     python3 decode_ssle_3d.py raw_scattering/layers \\"
echo -e "         --cols $COLS --rows $ROWS --layers $LAYERS --ecc $ECC --levels 4"
echo ""
echo -e "     ${BOLD}For 2D flat PNG:${RESET}"
echo -e "     python3 decode_ssle.py raw_scattering/capture.png \\"
echo -e "         --cols $COLS --rows $ROWS --ecc $ECC --levels 4"
echo ""
echo -e "     ${DIM}Use the exact --cols / --rows / --layers values printed by make_stl.sh${RESET}"
echo ""
note "Recovered file lands in the ${BOLD}output/${RESET} directory."
echo ""

step "Troubleshooting decoder failures:"
echo ""
echo -e "     ${YELLOW}RS ECC errors / bad magic:${RESET}"
echo -e "     • Try adjusting --threshold (default 80)"
echo -e "       Dim dots → lower it (try 60).  Noisy background → raise it (try 100)."
echo -e "     • Retake snapshot with better raking light"
echo -e "     • Confirm xTool was in Grayscale mode (not Bitmap/Jarvis)"
echo ""
echo -e "     ${YELLOW}Fiducials not found:${RESET}"
echo -e "     • Crystal must be flat and square — blu-tack a corner if it rocks"
echo -e "     • Improve lighting and retake snapshot"
echo -e "     • Try --threshold 120+ to make fiducial squares stand out"
echo ""
echo -e "     ${YELLOW}CRC fails after RS passes:${RESET}"
echo -e "     • Severe corruption — check crystal wasn't moved between write passes"
echo -e "     • For True 5D: verify 4 distinct gray shades visible in snapshot"
echo ""

# ══════════════════════════════════════════════════════════════════════════════
# DONE
# ══════════════════════════════════════════════════════════════════════════════

section "Setup Complete"

echo -e "  ${GREEN}${BOLD}You now have everything you need to write and read glass.${RESET}"
echo ""
echo -e "  ${BOLD}Day-to-day commands:${RESET}"
echo ""
echo -e "  ${GREEN}Encode a file to STL:${RESET}"
echo      "    bash make_stl.sh myfile.txt"
echo ""
echo -e "  ${GREEN}Capture a snapshot (after engraving):${RESET}"
echo      "    python3 capture_scattering.py --source xtool --file snapshot.jpg"
echo ""
echo -e "  ${GREEN}Decode a 3D disc:${RESET}"
echo      "    python3 decode_ssle_3d.py raw_scattering/layers --cols 500 --rows 500 --layers 5 --levels 4"
echo ""
echo -e "  ${GREEN}Decode a 2D disc:${RESET}"
echo      "    python3 decode_ssle.py raw_scattering/capture.png --cols 500 --rows 500 --levels 4"
echo ""
echo -e "  ${GREEN}Test pipeline (no hardware):${RESET}"
echo      "    python3 test_pipeline.py"
echo ""
echo -e "  ${DIM}Full docs: github.com/mrdulasolutions/EternalDrive-IndieHack${RESET}"
echo -e "  ${DIM}Issues:    github.com/mrdulasolutions/EternalDrive-IndieHack/issues${RESET}"
echo ""
echo -e "  Built live with Grok + Claude. No gatekeepers. Only build."
echo ""
