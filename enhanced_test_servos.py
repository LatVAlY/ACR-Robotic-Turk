from adafruit_servokit import ServoKit
import time

kit = ServoKit(channels=16)

print("Power check: Setting servo 0 to 90°...")
kit.servo[0].angle = 90
time.sleep(2)
read_angle = kit.servo[0].angle
print(f"Read angle: {read_angle}")

print("Slow sweep: 90° to 0°...")
for a in range(90, 0, -5):
    kit.servo[0].angle = a
    time.sleep(0.3)
time.sleep(1)

print("0° to 180°...")
for a in range(0, 181, 5):
    kit.servo[0].angle = a
    time.sleep(0.3)
time.sleep(1)

print("Back to 90°...")
kit.servo[0].angle = 90
time.sleep(1)

print("Test done — did it move? Read angle was {read_angle}.")
if read_angle is not None:
    print("✅ Communication good — check servo wiring/power.")
else:
    print("❌ Communication bad — check I2C.")