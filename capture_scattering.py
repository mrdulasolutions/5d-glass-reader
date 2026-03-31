from picamera2 import Picamera2
import cv2
import os

picam2 = Picamera2()
config = picam2.create_still_configuration(main={"size": (4056, 3040)})
picam2.configure(config)
picam2.start()

os.makedirs("raw_scattering", exist_ok=True)

print("📸 Position the glass disc under the camera and press Enter to capture...")
input()
img = picam2.capture_array()
cv2.imwrite("raw_scattering/capture.png", img)
print("✅ Saved raw_scattering/capture.png")

picam2.stop()
print("Capture done. Run decode_ssle.py next.")
