from adafruit_servokit import ServoKit
import math
import time
import sys
import os

# Add parent directory to Python path to import shared module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.utils import load_json

class MotionController:
    def __init__(self):
        self.kit = ServoKit(channels=16)
        # Use absolute path to config file
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'shared', 'config.json')
        self.config = load_json(config_path)
        self.arm_lengths = self.config['arm_lengths']  # e.g., {'l1': 5, 'l2': 7, 'l3': 3} cm
        self.square_size = self.config['square_size_cm']  # 2.5 cm per square
        for i in range(6):
            self.kit.servo[i].set_pulse_width_range(500, 2500)
        # New state vars
        self.state = 'unfolded'  # 'folded' or 'unfolded'
        self.power_on = True
        self.rotation_enabled = True
        self.init_servos()  # Wake servos to set initial angles

    def init_servos(self):
        for i in range(6):
            self.kit.servo[i].angle = 90  # Set to neutral to avoid None
            time.sleep(0.2)  # Short pause for stability

    def inverse_kinematics(self, x, y, z):
        # Base rotation (theta1)
        theta1 = math.degrees(math.atan2(y, x))
        
        # Distance in arm plane (r = projection on xy, d = full reach)
        r = math.sqrt(x**2 + y**2)
        d = math.sqrt(r**2 + (z - self.arm_lengths['l3'])**2)
        
        # Elbow angle (theta3) using law of cosines
        cos_theta3 = (self.arm_lengths['l1']**2 + self.arm_lengths['l2']**2 - d**2) / (2 * self.arm_lengths['l1'] * self.arm_lengths['l2'])
        theta3 = math.degrees(math.acos(max(min(cos_theta3, 1), -1)))
        
        # Shoulder angle (theta2)
        sin_theta3 = math.sin(math.radians(theta3))
        cos_theta3 = math.cos(math.radians(theta3))
        theta2 = math.degrees(math.atan2(z - self.arm_lengths['l3'], r)) - math.degrees(math.atan2(self.arm_lengths['l2'] * sin_theta3, self.arm_lengths['l1'] + self.arm_lengths['l2'] * cos_theta3))
        
        # Wrist angles for gripper down
        theta4 = 0  # Rotate neutral
        theta5 = 45  # Pitch down for pick
        theta6 = 0  # Gripper open
        
        # Clamp angles to servo limits (0-180)
        angles = [max(0, min(180, a)) for a in [theta1, theta2, theta3, theta4, theta5, theta6]]
        return angles

    def ease_to_angle(self, servo_id, start, end, steps=20):
        if start is None:
            start = 90  # Fallback if initial angle not set
        for step in range(steps):
            angle = start + (end - start) * step / steps
            self.kit.servo[servo_id].angle = angle
            time.sleep(0.05)  # 50ms/step = 1 sec total

    def move_to_square(self, square, z_hover=5, z_pick=1):
        # Map square to (x,y) (board centered at 0,0)
        col = ord(square[0]) - ord('a')
        row = int(square[1]) - 1
        x = (col + 0.5) * self.square_size - (7 * self.square_size / 2)  # Center offset
        y = (row + 0.5) * self.square_size - (7 * self.square_size / 2)
        
        # Hover position
        angles_hover = self.inverse_kinematics(x, y, z_hover)
        for i in range(6):
            self.ease_to_angle(i, self.kit.servo[i].angle, angles_hover[i])
        time.sleep(0.5)
        
        # Pick position
        angles_pick = self.inverse_kinematics(x, y, z_pick)
        for i in range(6):
            self.ease_to_angle(i, self.kit.servo[i].angle, angles_pick[i])
        time.sleep(0.5)

    def pick_up_piece(self):
        self.ease_to_angle(5, self.kit.servo[5].angle, 90)  # Close gripper
        time.sleep(0.5)

    def release_piece(self):
        self.ease_to_angle(5, self.kit.servo[5].angle, 0)  # Open gripper
        time.sleep(0.5)

    def home_position(self):
        for i in range(6):
            self.ease_to_angle(i, self.kit.servo[i].angle, 90)
        time.sleep(1)

    def execute_move(self, from_square, to_square):
        try:
            self.home_position()
            self.move_to_square(from_square)
            self.pick_up_piece()
            self.move_to_square(to_square)
            self.release_piece()
            self.home_position()
            return True
        except Exception as e:
            print(f"Motion error: {e} — retrying home")
            self.home_position()
            return False

    # NEW: Fold to storage (power off, lock rotation)
    def fold_to_position(self):
        if self.state == 'unfolded' and self.power_on:
            print("Folding to storage position...")
            # Park arm safely
            self.home_position()
            # Fold case servos (tune channels for your hinge mechanism)
            for i in [10, 11, 12]:  # Example: 3 servos for fold
                self.ease_to_angle(i, self.kit.servo[i].angle, 0)  # Close/fold angle
            time.sleep(1)
            self.state = 'folded'
            self.rotation_enabled = False
            self.turn_off()
            print("Robot folded and powered off.")
        else:
            print("Cannot fold: already folded or off.")

    # NEW: Unfold to play (power on, enable rotation)
    def unfold_to_normal(self):
        if self.state == 'folded':
            print("Unfolding to normal position...")
            # Unfold case servos
            for i in [10, 11, 12]:
                self.ease_to_angle(i, self.kit.servo[i].angle, 90)  # Open/unfold angle
            time.sleep(1)
            self.state = 'unfolded'
            self.wake_up()
            self.rotation_enabled = True
            self.init_servos()  # Re-wake arm
            print("Robot unfolded and powered on.")
        else:
            print("Cannot unfold: already unfolded.")

    # NEW: Soft power off (park all servos)
    def turn_off(self):
        if self.power_on:
            self.power_on = False
            # Park everything safe
            for i in range(16):  # All channels
                self.kit.servo[i].angle = 90
            # Optional: os.system('sudo shutdown -h now') for full Pi off
            print("Power off: Servos parked, peripherals disabled.")

    # NEW: Soft power on (re-init)
    def wake_up(self):
        if not self.power_on:
            self.power_on = True
            print("Power on: Systems initialized, servos active.")
            # Add camera/vision re-start here if integrated

    # NEW: Rotate board (locked if folded/off)
    def attempt_rotate(self, degrees=180):
        if self.state == 'folded' or not self.power_on:
            print("Cannot rotate: Robot is folded or powered off!")
            return False
        if not self.rotation_enabled:
            print("Rotation not enabled.")
            return False
        print(f"Rotating board {degrees} degrees...")
        # Rotation servo (tune channel)
        rotation_id = 6  # Your board spin servo
        start_angle = self.kit.servo[rotation_id].angle
        target_angle = (start_angle + degrees) % 360  # Mod 360, but clamp 0-180 if needed
        self.ease_to_angle(rotation_id, start_angle, target_angle)
        time.sleep(1)  # Rotate time
        print("Rotation complete.")
        return True

# Quick Usage Example (add to your main script)
if __name__ == "__main__":
    mc = MotionController()
    # Experiment sequence
    mc.fold_to_position()  # Fold & off
    mc.attempt_rotate()  # Fails
    mc.unfold_to_normal()  # Unfold & on
    mc.attempt_rotate()  # Succeeds
    # For chess: if needs_rotation(from_square, to_square): mc.attempt_rotate()
    mc.execute_move('e2', 'e4')  # Normal move