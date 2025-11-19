import unittest
import time
import traceback
from motion import MotionController

class TestMotionController(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("=== Starting Safer Tests ===")
        cls.mc = MotionController()
        cls.log_file = "motion_test_log.txt"
        with open(cls.log_file, 'w') as f:
            f.write("Safe Motion Test Log - " + time.strftime("%Y-%m-%d %H:%M:%S") + "\n\n")

    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
        with open(self.log_file, 'a') as f:
            f.write(f"[{timestamp}] {message}\n")

    def test_servo_sweep(self):
        self.log("Safe servo sweep (clamped angles)...")
        for ch in range(16):
            try:
                self.log(f"ch{ch}: To 0°...")
                self.mc.ease_to_angle(ch, None, 0)
                time.sleep(1.5)
                self.log(f"ch{ch} at 0° - OBSERVE & NOTE: What moved? (arm lift, hinge, gripper?)")
                self.mc.ease_to_angle(ch, None, 90)
                time.sleep(0.5)
                self.log(f"ch{ch} parked.")
            except Exception as e:
                self.log(f"ch{ch} error (skipped): {e}")
        self.log("Sweep done—UPDATE CONFIG with observations!")

    def test_fold_sequence(self):
        self.log("Safe fold test...")
        try:
            self.mc.fold_to_position()
            self.log("Fold done - OBSERVE: Vertical stand? Hinges closed?")
            time.sleep(2)
        except Exception as e:
            self.log(f"Fold error (continued): {e}")

    def test_unfold_sequence(self):
        self.log("Safe unfold test...")
        try:
            self.mc.unfold_to_normal(force=True)
            self.log("Unfold done - OBSERVE: Ready pose (horizontal OK for now)?")
            time.sleep(2)
        except Exception as e:
            self.log(f"Unfold error: {e}")

    def test_rotate(self):
        self.log("Safe rotate...")
        try:
            self.mc.attempt_rotate(180)
            self.log("Rotate done - OBSERVE: Board spin?")
        except Exception as e:
            self.log(f"Rotate error: {e}")

    def test_sample_move(self):
        self.log("Safe sample move (e2-e4)...")
        try:
            success = self.mc.execute_move('e2', 'e4')
            self.log(f"Move {'success' if success else 'failed'} - OBSERVE: Gripper action?")
        except Exception as e:
            self.log(f"Move error: {e}")

    def test_error_handling(self):
        self.log("Error handling...")
        try:
            self.mc.ease_to_angle(0, None, 200)  # Bad angle
            self.fail("No clamp on bad angle!")
        except ValueError:
            self.log("Clamp caught bad angle - good!")

    @classmethod
    def tearDownClass(cls):
        cls.mc.turn_off()  # Safe park
        print("\n=== Tests Done. Power cycle if frozen! ===")

if __name__ == '__main__':
    unittest.main(verbosity=2, exit=False)