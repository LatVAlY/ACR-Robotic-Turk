from adafruit_servokit import ServoKit
import time

class ServoTester:
    def __init__(self):
        self.kit = ServoKit(channels=16)
        # Set safe pulse width range for all servos
        for i in range(16):
            try:
                self.kit.servo[i].set_pulse_width_range(500, 2500)
            except:
                pass
        
        # Discovered servo mapping (update as you test)
        self.servo_map = {
            'grip_mouth': None,    # Channel TBD
            'grip': None,          # Channel TBD
            'body_1': None,        # Channel TBD
            'body_2': None,        # Channel TBD
            'body_3': None,        # Channel TBD
            'base_rotation': None  # Channel TBD
        }
    
    def safe_angle(self, channel, angle):
        """Move servo to angle safely"""
        angle = max(0, min(180, angle))
        try:
            self.kit.servo[channel].angle = angle
            print(f"✓ Ch{channel} → {angle}°")
            return True
        except Exception as e:
            print(f"✗ Ch{channel} failed: {e}")
            return False
    
    def test_channel(self, channel):
        """Test a single channel with sweep"""
        print(f"\n--- Testing Channel {channel} ---")
        print("Moving to 90° (center)...")
        self.safe_angle(channel, 90)
        time.sleep(1)
        
        print("Sweeping 90° → 120° → 90° → 60° → 90°")
        for angle in [120, 90, 60, 90]:
            self.safe_angle(channel, angle)
            time.sleep(0.5)
        print("Done!\n")
    
    def test_all_channels(self):
        """Quick test all channels 0-15"""
        print("\n=== TESTING ALL CHANNELS ===")
        for ch in range(16):
            print(f"\nChannel {ch}:")
            self.safe_angle(ch, 90)
            time.sleep(0.3)
        print("\n=== ALL CENTERED AT 90° ===")
    
    def park_all(self):
        """Park all servos to 90° (safe middle position)"""
        print("\n=== PARKING ALL SERVOS ===")
        for ch in range(16):
            self.safe_angle(ch, 90)
        print("All parked at 90°\n")
    
    def interactive_test(self):
        """Interactive testing mode"""
        print("\n" + "="*50)
        print("SERVO TESTER - Interactive Mode")
        print("="*50)
        print("\nCommands:")
        print("  test <channel>     - Test single channel (e.g., 'test 0')")
        print("  angle <ch> <deg>   - Set angle (e.g., 'angle 5 45')")
        print("  scan               - Test all channels 0-15")
        print("  park               - Park all to 90°")
        print("  map <name> <ch>    - Map servo (e.g., 'map grip 5')")
        print("  show               - Show current mapping")
        print("  quit               - Exit")
        print("="*50 + "\n")
        
        while True:
            try:
                cmd = input("servo> ").strip().lower().split()
                if not cmd:
                    continue
                
                if cmd[0] == 'quit':
                    self.park_all()
                    break
                
                elif cmd[0] == 'test' and len(cmd) == 2:
                    ch = int(cmd[1])
                    self.test_channel(ch)
                
                elif cmd[0] == 'angle' and len(cmd) == 3:
                    ch = int(cmd[1])
                    angle = int(cmd[2])
                    self.safe_angle(ch, angle)
                
                elif cmd[0] == 'scan':
                    self.test_all_channels()
                
                elif cmd[0] == 'park':
                    self.park_all()
                
                elif cmd[0] == 'map' and len(cmd) == 3:
                    name = cmd[1]
                    ch = int(cmd[2])
                    if name in self.servo_map:
                        self.servo_map[name] = ch
                        print(f"✓ Mapped '{name}' → Channel {ch}")
                    else:
                        print(f"✗ Unknown servo name. Use: {list(self.servo_map.keys())}")
                
                elif cmd[0] == 'show':
                    print("\nCurrent Mapping:")
                    for name, ch in self.servo_map.items():
                        status = f"Ch{ch}" if ch is not None else "NOT SET"
                        print(f"  {name:15} → {status}")
                    print()
                
                else:
                    print("Unknown command. Type 'quit' to exit.\n")
            
            except ValueError:
                print("Invalid input. Use numbers for channels/angles.\n")
            except KeyboardInterrupt:
                print("\n\nExiting...")
                self.park_all()
                break
            except Exception as e:
                print(f"Error: {e}\n")

if __name__ == "__main__":
    tester = ServoTester()
    tester.interactive_test()