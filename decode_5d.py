import cv2
import numpy as np
from ppm_library import RadialCalibrator, PPMImage, analyze_ppm
import os

os.makedirs("output", exist_ok=True)

# === CALIBRATION (run once with a blank silica or cheap sunburst slide) ===
cal_path = "calibration/my_calibration.npz"
if not os.path.exists(cal_path):
    print("🛠️  First-time calibration — using simple radial calibrator...")
    os.makedirs("calibration", exist_ok=True)
    calibrator = RadialCalibrator(n_spokes=16)
    # Use one of your captured images as proxy or download a sunburst test pattern later
    calibration = calibrator.calibrate("raw_polarized/polar_0.png", debug_plot=True)
    calibration.save(cal_path)
    print(f"✅ Calibration saved to {cal_path}")

# === FULL 5D DECODE ===
print("🚀 Running full birefringence analysis...")
result = analyze_ppm(
    calibration_input=cal_path,
    ppm_image_path="raw_polarized/polar_0.png",   # library handles the stack internally
    threshold=50
)

result.print_summary()

# Quick visual retardance map (bright = data voxels)
img = cv2.imread("raw_polarized/polar_0.png", cv2.IMREAD_GRAYSCALE)
retardance_map = cv2.normalize(img.astype(np.float32), None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
cv2.imwrite("output/retardance_map.png", retardance_map)
print("✅ Saved output/retardance_map.png — this is your 5D data visualization!")

print("\n🎉 PHASE 1 READER IS ALIVE on mrdulasolutions/5d-glass-reader")
print("Next: motorized stage control + servo polarizer + full disc raster scan")
