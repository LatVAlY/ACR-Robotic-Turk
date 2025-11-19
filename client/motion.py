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
        self.channels = self.config.get('servo_channels', {})  # Load channels
        self.fold_angles = self.config.get('fold_angles', {'park': 90, 'stand_up': 0, 'lay_down': 180})
        self.kit = ServoKit(channels=16)
        for i in range(6):  # Arm only
            try:
                self.kit.servo[i].set_pulse_width_range(500, 2500)
            except Exception as e:
                print(f"Warning: Servo {i} range set failed: {e}")
        # New state vars
        self.state = 'unfolded'  # 'folded' or 'unfolded'
        self.power_on = True
        self.rotation_enabled = True
        self.init_servos()  # Wake servos to set initial angles

    def init_servos(self):
        print("Initializing servos to park...")
        for ch in range(16):  # All safe
            try:
                self.kit.servo[ch].angle = self.fold_angles['park']
            except Exception as e:
                print(f"Warning: Servo {ch} park failed: {e}")
        time.sleep(0.5)

    def home_position(self):
        print("Homing arm...")
        for i in range(6):
            try:
                self.ease_to_angle(i, self.kit.servo[i].angle, self.fold_angles['park'])
            except Exception as e:
                print(f"Home servo {i} failed: {e}")
        # Shoulder stand-up (use config ch or fallback 1)
        shoulder_ch = self.channels.get('shoulder', 1)
        try:
            self.ease_to_angle(shoulder_ch, self.kit.servo[shoulder_ch].angle, self.fold_angles['stand_up'])
        except Exception as e:
            print(f"Shoulder stand-up failed: {e}")
        time.sleep(1)

    def fold_to_position(self):
        if self.state == 'unfolded' and self.power_on:
            print("Folding...")
            self.home_position()
            hinge_chs = self.channels.get('fold_hinges', [13,14,15])
            for ch in hinge_chs:
                try:
                    self.ease_to_angle(ch, self.kit.servo[ch].angle, 0)  # Close
                except Exception as e:
                    print(f"Hinge {ch} failed: {e}")
            time.sleep(1)
            self.state = 'folded'
            self.rotation_enabled = False
            self.turn_off()
            print("Fold complete.")
        else:
            print("Cannot fold.")

    def unfold_to_normal(self, force=False):
        if self.state == 'folded' or force:
            print("Unfolding...")
            hinge_chs = self.channels.get('fold_hinges', [13,14,15])
            for ch in hinge_chs:
                try:
                    self.ease_to_angle(ch, self.kit.servo[ch].angle, self.fold_angles['park'])  # Open
                except Exception as e:
                    print(f"Hinge {ch} failed: {e}")
            time.sleep(1)
            shoulder_ch = self.channels.get('shoulder', 1)
            try:
                self.ease_to_angle(shoulder_ch, self.kit.servo[shoulder_ch].angle, self.fold_angles['park'])  # Ready
            except Exception as e:
                print(f"Shoulder ready failed: {e}")
            self.state = 'unfolded'
            self.wake_up()
            self.rotation_enabled = True
            self.init_servos()
            print("Unfold complete.")
        else:
            print("Already unfolded.")

    def turn_off(self):
        if self.power_on:
            self.power_on = False
            for ch in range(16):
                try:
                    self.kit.servo[ch].angle = self.fold_angles['park']
                except Exception:
                    pass  # Ignore
            print("Power off: Parked.")

    def wake_up(self):
        if not self.power_on:
            self.power_on = True
            self.init_servos()
            print("Power on.")

    def attempt_rotate(self, degrees=180):
        if self.state == 'folded' or not self.power_on:
            print("Cannot rotate.")
            return False
        rot_ch = self.channels.get('rotation', 6)
        start = self.kit.servo[rot_ch].angle
        target = max(0, min(180, (start + degrees) % 360))
        self.ease_to_angle(rot_ch, start, target)
        print("Rotation done.")
        return True           

    def inverse_kinematics(self, x, y, z):
        try:
            theta1 = math.degrees(math.atan2(y, x))
            r = math.sqrt(x**2 + y**2)
            d = math.sqrt(r**2 + (z - self.arm_lengths['l3'])**2)
            cos_theta3 = (self.arm_lengths['l1']**2 + self.arm_lengths['l2']**2 - d**2) / (2 * self.arm_lengths['l1'] * self.arm_lengths['l2'])
            if not -1 <= cos_theta3 <= 1:  # Invalid reach
                raise ValueError("IK unreachable position")
            theta3 = math.degrees(math.acos(cos_theta3))
            sin_theta3 = math.sin(math.radians(theta3))
            cos_theta3 = math.cos(math.radians(theta3))
            theta2 = math.degrees(math.atan2(z - self.arm_lengths['l3'], r)) - math.degrees(math.atan2(self.arm_lengths['l2'] * sin_theta3, self.arm_lengths['l1'] + self.arm_lengths['l2'] * cos_theta3))
            theta4 = 0
            theta5 = 45
            theta6 = 0
            angles = [max(0, min(180, a)) for a in [theta1, theta2, theta3, theta4, theta5, theta6]]
            return angles
        except Exception as e:
            print(f"IK failed ({e}) - fallback to park")
            return [90] * 6  # Safe park

    def ease_to_angle(self, servo_id, start, end, steps=20):
        if start is None:
            start = 90
        for step in range(steps):
            angle = start + (end - start) * step / steps
            clamped = max(0, min(180, angle))  # CRITICAL: Clamp here
            try:
                self.kit.servo[servo_id].angle = clamped
            except ValueError as e:
                print(f"Clamped angle {clamped} still failed on servo {servo_id}: {e}")
            time.sleep(0.05)

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
            self.home_position()  # Safe retry
            return False

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