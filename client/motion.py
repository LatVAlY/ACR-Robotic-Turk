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
        for i in range(6):
            self.kit.servo[i].set_pulse_width_range(500, 2500)
        # New state vars
        self.state = 'unfolded'  # 'folded' or 'unfolded'
        self.power_on = True
        self.rotation_enabled = True
        self.init_servos()  # Wake servos to set initial angles

    def init_servos(self):
        # Park arm + hinges
        for name, ch in self.channels.items():
            if name == 'fold_hinges':
                for c in ch:
                    self.kit.servo[c].angle = self.fold_angles['park']
            else:
                self.kit.servo[ch].angle = self.fold_angles['park']
        time.sleep(0.5)

    def home_position(self):
        # Home arm (0-5) + lift shoulder to stand_up
        for i in range(6):
            self.ease_to_angle(i, self.kit.servo[i].angle, self.fold_angles['park'])
        shoulder_ch = self.channels['shoulder']
        self.ease_to_angle(shoulder_ch, self.kit.servo[shoulder_ch].angle, self.fold_angles['stand_up'])
        time.sleep(1)

    def fold_to_position(self):
        if self.state == 'unfolded' and self.power_on:
            print("Folding to storage position...")
            self.home_position()  # Stands up first
            hinge_chs = self.channels['fold_hinges']
            for ch in hinge_chs:
                self.ease_to_angle(ch, self.kit.servo[ch].angle, 0)  # Fold closed
            time.sleep(1)
            self.state = 'folded'
            self.rotation_enabled = False
            self.turn_off()
            print("Robot folded (standing) and off.")
        else:
            print("Cannot fold.")

    def unfold_to_normal(self, force=False):
        if self.state == 'folded' or force:
            print("Unfolding to normal position...")
            hinge_chs = self.channels['fold_hinges']
            for ch in hinge_chs:
                self.ease_to_angle(ch, self.kit.servo[ch].angle, self.fold_angles['park'])
            time.sleep(1)
            shoulder_ch = self.channels['shoulder']
            self.ease_to_angle(shoulder_ch, self.kit.servo[shoulder_ch].angle, self.fold_angles['park'])
            self.state = 'unfolded'
            self.wake_up()
            self.rotation_enabled = True
            self.init_servos()
            print("Robot unfolded and on.")
        else:
            print("Already unfolded—no action.") 

    def turn_off(self):
        if self.power_on:
            self.power_on = False
            for ch in range(16):
                self.kit.servo[ch].angle = self.fold_angles['park']
            print("Power off: All parked.")

    def wake_up(self):
        if not self.power_on:
            self.power_on = True
            self.init_servos()
            print("Power on.")

    def attempt_rotate(self, degrees=180):
        if self.state == 'folded' or not self.power_on:
            print("Cannot rotate.")
            return False
        rot_ch = self.channels['rotation']
        start = self.kit.servo[rot_ch].angle
        target = min(180, (start + degrees) % 360)
        self.ease_to_angle(rot_ch, start, target)
        print("Rotation done.")
        return True              

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