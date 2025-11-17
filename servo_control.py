from adafruit_servokit import ServoKit
import json
import time

# Initialize PCA9685 (your setup: channels=16, address=0x40)
kit = ServoKit(channels=16)

# Set pulse range for SG90/MG90S servos (do this once)
for i in range(6):
    kit.servo[i].set_pulse_width_range(500, 2500)

def load_movements():
    """Load chess square angles from JSON"""
    with open('controlMovements.json', 'r') as f:
        return json.load(f)

def move_to_square(square):
    """Move arm to chess square (e.g., 'a1') using 3 main joints (0-2).
    Extend for full 6-DOF if needed (wrist/gripper on 3-5).
    """
    movements = load_movements()
    if square not in movements:
        print(f"Unknown square: {square}")
        return
    
    angles = movements[square]  # e.g., [190, 185, 17] for base, shoulder, elbow
    
    # Move joints 0-2 (base, shoulder, elbow) to angles
    for i, angle in enumerate(angles):
        kit.servo[i].angle = angle
        time.sleep(0.5)  # Slow move to avoid strain
    
    # Optional: Position wrist/gripper (joints 3-5) to "pick" pose
    kit.servo[3].angle = 90  # Wrist rotate: neutral
    kit.servo[4].angle = 90  # Wrist pitch: down
    kit.servo[5].angle = 0   # Gripper: open
    
    print(f"Moved to {square}: angles {angles}")

def pick_up_piece():
    """Close gripper to pick piece"""
    kit.servo[5].angle = 90  # Close gripper
    time.sleep(1)

def release_piece():
    """Open gripper to release"""
    kit.servo[5].angle = 0   # Open
    time.sleep(1)

def home_position():
    """Return arm to start (all neutral)"""
    for i in range(6):
        kit.servo[i].angle = 90
    time.sleep(2)