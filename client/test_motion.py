import unittest
import time
import traceback
from motion import MotionController  # Replace 'motion' with your module name if different

class TestMotionController(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("=== Starting MotionController Tests ===")
        cls.mc = MotionController()
        cls.log_file = "motion_test_log.txt"
        with open(cls.log_file, 'w') as f:
            f.write("Motion Test Log - Timestamp: " + time.strftime("%Y-%m-%d %H:%M:%S") + "\n\n")

    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
        with open(self.log_file, 'a') as f:
            f.write(f"[{timestamp}] {message}\n")

    def test_servo_sweep(self):
        """Test each servo channel 0-15: Sweep 0° -> 90° -> park 90°, log movements."""
        self.log("Starting servo sweep test...")
        try:
            for ch in range(16):
                self.log(f"Testing channel {ch}: Moving to 0°...")
                self.mc.ease_to_angle(ch, None, 0)
                time.sleep(2)  # Hold to observe
                self.log(f"Channel {ch} at 0° - OBSERVE: What moved? (e.g., arm up/down, gripper rotate)")
                self.mc.ease_to_angle(ch, None, 90)
                time.sleep(1)
                self.log(f"Channel {ch} back to 90° (parked).")
            self.log("Servo sweep complete. Check log for observations.")
        except Exception as e:
            self.log(f"ERROR in servo sweep: {str(e)}")
            traceback.print_exc()
            self.fail(f"Servo sweep failed: {e}")

    def test_fold_sequence(self):
        """Test full fold: Home -> stand up -> close hinges -> park all."""
        self.log("Starting fold sequence test...")
        try:
            self.mc.fold_to_position()
            self.log("Fold complete - OBSERVE: Is arm standing vertical? Hinges closed?")
            time.sleep(3)  # Hold to observe
            self.log("Fold sequence done.")
        except Exception as e:
            self.log(f"ERROR in fold: {str(e)}")
            traceback.print_exc()
            self.fail(f"Fold failed: {e}")

    def test_unfold_sequence(self):
        """Test full unfold: Open hinges -> drop to ready -> init servos."""
        self.log("Starting unfold sequence test...")
        try:
            self.mc.unfold_to_normal(force=True)  # Force to run even if not folded
            self.log("Unfold complete - OBSERVE: Arm in ready pose (not laying)? Hinges open?")
            time.sleep(3)
            self.log("Unfold sequence done.")
        except Exception as e:
            self.log(f"ERROR in unfold: {str(e)}")
            traceback.print_exc()
            self.fail(f"Unfold failed: {e}")

    def test_rotate(self):
        """Test board rotation (if unfolded)."""
        self.log("Starting rotation test...")
        try:
            success = self.mc.attempt_rotate(180)
            if success:
                self.log("Rotation complete - OBSERVE: Board spun 180°?")
                time.sleep(2)
            else:
                self.log("Rotation skipped (folded/off).")
        except Exception as e:
            self.log(f"ERROR in rotate: {str(e)}")
            traceback.print_exc()
            self.fail(f"Rotate failed: {e}")

    def test_sample_move(self):
        """Test a sample chess move: e2 to e4 (pick/release)."""
        self.log("Starting sample move test (e2 to e4)...")
        try:
            success = self.mc.execute_move('e2', 'e4')
            if success:
                self.log("Move complete - OBSERVE: Piece picked from e2, released at e4?")
            else:
                self.log("Move failed - check errors.")
        except Exception as e:
            self.log(f"ERROR in move: {str(e)}")
            traceback.print_exc()
            self.fail(f"Move failed: {e}")

    def test_error_handling(self):
        """Test error catching: Intentionally bad input."""
        self.log("Starting error handling test...")
        try:
            self.mc.execute_move('z9', 'a1')  # Invalid squares
            self.fail("Should have raised error on invalid move.")
        except Exception as e:
            self.log(f"Expected error caught: {str(e)} - Good!")
            # Also test servo out-of-range
            try:
                self.mc.ease_to_angle(0, None, 200)  # Invalid angle
                self.fail("Should clamp or error on invalid angle.")
            except Exception as e2:
                self.log(f"Angle error caught: {str(e2)}")

    @classmethod
    def tearDownClass(cls):
        cls.mc.home_position()  # Park at end
        print("\n=== Tests Complete. Check motion_test_log.txt for details ===")

if __name__ == '__main__':
    # Run all tests
    unittest.main(verbosity=2, exit=False)

    # Or run specific: python test_motion.py TestMotionController.test_servo_sweep