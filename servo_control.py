from adafruit_servokit import ServoKit
import json
import time

kit = ServoKit(channels=16)

# Set for SG90 servos
for i in range(6):
    kit.servo[i].set_pulse_width_range(500, 2500)

def load_movements():
    with open('controlMovements.json', 'r') as f:
        return json.load(f)

def move_to_square(square):
    movements = load_movements()
    if square not in movements:
        print(f"Unknown square: {square}")
        return
    angles = movements[square]
    for i, angle in enumerate(angles[:3]):  # Base, shoulder, elbow
        kit.servo[i].angle = angle
        time.sleep(0.5)
    # Wrist/gripper neutral
    kit.servo[3].angle = 90
    kit.servo[4].angle = 90
    kit.servo[5].angle = 0  # Open
    print(f"Moved to {square}")

def pick_up():
    kit.servo[5].angle = 90  # Close gripper
    time.sleep(1)

def release():
    kit.servo[5].angle = 0  # Open
    time.sleep(1)

def home():
    for i in range(6):
        kit.servo[i].angle = 90
    time.sleep(2)