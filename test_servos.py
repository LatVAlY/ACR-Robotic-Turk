from adafruit_servokit import ServoKit
import time

kit = ServoKit(channels=16)

print("Testing servo 0 (base)...")
print("Setting to 90° (center)...")
kit.servo[0].angle = 90
time.sleep(1)
current_angle = kit.servo[0].angle
print(f"Current angle: {current_angle}")  # Should be 90.0, not None

print("Sweeping to 0°...")
kit.servo[0].angle = 0
time.sleep(1)

print("Sweeping to 180°...")
kit.servo[0].angle = 180
time.sleep(1)

print("Back to 90°...")
kit.servo[0].angle = 90
time.sleep(1)

print("Sweep complete — did servo 0 move smoothly?")
if current_angle is not None:
    print("✅ ServoKit is working!")
else:
    print("❌ Issue detected — check wiring/power.")