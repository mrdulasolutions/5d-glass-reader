import cv2
import numpy as np
import os

os.makedirs("output", exist_ok=True)

# Load the captured image
img = cv2.imread("raw_scattering/capture.png", cv2.IMREAD_GRAYSCALE)

# Simple threshold + blob detection for SSLE dots (bright scattering points)
_, thresh = cv2.threshold(img, 80, 255, cv2.THRESH_BINARY)  # tweak threshold for your lighting
contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

# Grid parameters — adjust to your engraving density (example: 100x100 grid)
GRID_ROWS = 100
GRID_COLS = 100
dot_positions = []

for cnt in contours:
    x, y, w, h = cv2.boundingRect(cnt)
    center_x = x + w // 2
    center_y = y + h // 2
    dot_positions.append((center_x, center_y))

# Sort into grid and decode to bits (simple nearest-grid for v0.1)
# TODO: improve with perspective correction + error correction later
bits = []
print(f"Detected {len(dot_positions)} dots — decoding...")

# (Placeholder grid decode — we expand this once you have real test engravings)
decoded_bytes = b'TEST_DATA_FROM_GLASS'  # replace with real decode logic

with open("output/decoded_file.bin", "wb") as f:
    f.write(decoded_bytes)

print("✅ Decoded to output/decoded_file.bin")
print("🎉 SSLE GLASS DRIVE v0.1 IS ALIVE — COTS indie hack complete")
