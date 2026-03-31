#!/usr/bin/env python3
"""
capture_scattering.py — Capture a glass disc image for decoding.

Supports three capture sources:

  --source xtool  [FASTEST + EASIEST] ★ RECOMMENDED ★
      Load the K9/fused silica disc back into the xTool F2 Ultra.
      In xTool Studio: Camera icon → Snapshot → Save image.
      Then: python3 capture_scattering.py --source xtool --file snapshot.png
      Uses the machine's own dual 48MP cameras. No extra hardware needed.
      Hack: xTool Studio's snapshot saves a full-res camera JPEG/PNG you can
      feed directly to decode_ssle.py. The F2 Ultra is both writer AND reader.

  --source usb    [EASIEST standalone reader, ~$30]
      USB digital microscope or webcam plugged into any laptop or Pi.
      python3 capture_scattering.py --source usb --device 0
      Works on Mac, Windows, Linux. No Pi or special hardware needed.

  --source pi     [MOST ACCURATE — automated raster scanning]
      Raspberry Pi HQ Camera (IMX477) via picamera2.
      Combine with stage_control.py + scan_disc.py for full automated
      motorized raster scan across a large disc.
      python3 capture_scattering.py --source pi

  --source file   [use any existing image]
      Feed any image file directly (phone photo, screenshot, exported scan).
      python3 capture_scattering.py --source file --file my_photo.jpg

Usage:
    # xTool camera path (fastest, same machine):
    python3 capture_scattering.py --source xtool --file snapshot.png

    # USB microscope (easiest standalone):
    python3 capture_scattering.py --source usb

    # Pi HQ Camera (most accurate, automated):
    python3 capture_scattering.py --source pi

    # Existing image:
    python3 capture_scattering.py --source file --file my_scan.jpg
"""

import argparse
import os
import shutil
import sys
import time

DEFAULT_OUTPUT_DIR  = 'raw_scattering'
DEFAULT_OUTPUT_FILE = os.path.join(DEFAULT_OUTPUT_DIR, 'capture.png')


def capture_pi(output_file):
    """Raspberry Pi HQ Camera via picamera2. Most accurate — use with motorized stage."""
    try:
        from picamera2 import Picamera2
    except ImportError:
        print("ERROR: picamera2 not available. Are you on a Raspberry Pi?")
        print("       Try: --source usb  or  --source xtool")
        sys.exit(1)

    import cv2
    cam = Picamera2()
    config = cam.create_still_configuration(main={"size": (4056, 3040)})
    cam.configure(config)
    cam.start()
    time.sleep(0.5)

    print("[capture] Pi HQ Camera ready.")
    print("          Position the glass disc under the camera.")
    print("          Press Enter to capture...")
    input()

    img = cam.capture_array()
    cam.stop()
    cv2.imwrite(output_file, img)
    print(f"[capture] Saved → {output_file}")


def capture_usb(device, output_file):
    """USB digital microscope or webcam. Easiest standalone reader."""
    try:
        import cv2
    except ImportError:
        print("ERROR: opencv-python not installed. Run: pip install opencv-python")
        sys.exit(1)

    cap = cv2.VideoCapture(device)
    if not cap.isOpened():
        print(f"ERROR: Could not open camera device {device}")
        print(f"       Try a different --device index (0, 1, 2, ...)")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  4096)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 3072)

    print(f"[capture] USB camera device {device} ready.")
    print("          Position the glass disc under the camera.")
    print("          Press Enter to capture (or Ctrl+C to cancel)...")
    input()

    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        print("ERROR: Failed to capture frame from USB camera.")
        sys.exit(1)

    cv2.imwrite(output_file, frame)
    print(f"[capture] Saved → {output_file}")


def capture_xtool(src_file, output_file):
    """
    xTool F2 Ultra camera path — fastest + easiest, same machine for write AND read.

    How to get the snapshot from xTool Studio:
      1. Load your engraved K9 crystal / fused silica disc back into the F2 Ultra.
      2. Open xTool Studio → connect to machine.
      3. Click the Camera icon (top-right of work area) → 'Snapshot' or 'Take Photo'.
         The software saves a full-resolution JPEG/PNG of the workpiece.
      4. Note the saved file path and pass it with --file.

    Alternative (manual hack):
      - With disc loaded, screenshot the xTool Studio camera preview window.
      - Crop to the work area (remove the UI chrome).
      - Pass the cropped image with --file.

    The F2 Ultra's dual 48MP cameras can resolve dots at 100µm spacing.
    Tip: turn on a side-light (flashlight at a low angle) before snapping —
    scattering dots glow bright white under raking light.
    """
    if not src_file:
        print("ERROR: --source xtool requires --file <path to xTool Studio snapshot>")
        print()
        print("Steps:")
        print("  1. Load engraved K9 disc into xTool F2 Ultra")
        print("  2. xTool Studio → Camera icon → Snapshot → save file")
        print("  3. python3 capture_scattering.py --source xtool --file <saved_file>")
        sys.exit(1)

    if not os.path.exists(src_file):
        print(f"ERROR: File not found: {src_file}")
        sys.exit(1)

    shutil.copy2(src_file, output_file)
    print(f"[capture] xTool snapshot copied → {output_file}")
    print(f"          Ready for: python3 decode_ssle.py")


def capture_file(src_file, output_file):
    """Use any existing image file (phone photo, exported scan, screenshot)."""
    if not src_file:
        print("ERROR: --source file requires --file <path>")
        sys.exit(1)
    if not os.path.exists(src_file):
        print(f"ERROR: File not found: {src_file}")
        sys.exit(1)
    shutil.copy2(src_file, output_file)
    print(f"[capture] Image copied → {output_file}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Capture a glass disc image for decode_ssle.py'
    )
    parser.add_argument(
        '--source', choices=['xtool', 'usb', 'pi', 'file'], default='pi',
        help=(
            'xtool = xTool Studio snapshot [FASTEST+EASIEST] | '
            'usb = USB microscope/webcam | '
            'pi = Pi HQ Camera [MOST ACCURATE] | '
            'file = existing image'
        )
    )
    parser.add_argument('--file',   help='Image path (required for --source xtool or file)')
    parser.add_argument('--device', type=int, default=0,
                        help='USB camera device index (default: 0)')
    parser.add_argument('--output', '-o', default=DEFAULT_OUTPUT_FILE,
                        help=f'Output image path (default: {DEFAULT_OUTPUT_FILE})')
    args = parser.parse_args()

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)

    if args.source == 'pi':
        capture_pi(args.output)
    elif args.source == 'usb':
        capture_usb(args.device, args.output)
    elif args.source == 'xtool':
        capture_xtool(args.file, args.output)
    elif args.source == 'file':
        capture_file(args.file, args.output)

    print()
    print(f"Next: python3 decode_ssle.py {args.output}")
