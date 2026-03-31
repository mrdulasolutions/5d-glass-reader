from picamera2 import Picamera2
import cv2
import numpy as np
import time
import os

picam2 = Picamera2()
config = picam2.create_still_configuration(main={"size": (4056, 3040)})
picam2.configure(config)
picam2.start()

os.makedirs("raw_polarized", exist_ok=True)

angles = [0, 45, 90, 135]  # 4 angles = enough for full retardance + orientation in ppm_library
for angle in angles:
    print(f"🔄 Rotate analyzer to {angle}° then press Enter...")
    input()  # manual rotation for v0.1 (we add servo next)
    img = picam2.capture_array()
    cv2.imwrite(f"raw_polarized/polar_{angle}.png", img)
    print(f"✅ Saved raw_polarized/polar_{angle}.png")

picam2.stop()
print("Capture complete. Run decode_5d.py next.")
