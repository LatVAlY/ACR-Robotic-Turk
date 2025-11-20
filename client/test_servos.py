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
        
        # Discovered servo mapping (TESTED & CONFIRMED)
        self.servo_map = {
            'base': 0,           # Base rotation
            'grip': 1,           # Gripper open/close
            'grip_mouth': 2,     # Gripper mouth/jaw
            'body_1': 4,         # Body servo 1
            'body_2': 3,         # Body servo 2
        }
        
        # Position presets (adjust these as you test!)
        self.presets = {
            'park': {
                'base': 90,
                'grip': 90,
                'grip_mouth': 90,
                'body_1': 90,
                'body_2': 90,
            },
            'fold': {
                'base': 0,         # Will rotate here in sequence
                'grip': 45,        # Slightly closed
                'grip_mouth': 45,
                'body_1': 0,       # Fold down
                'body_2': 0,       # Fold down
            },
            'unfold': {
                'base': 90,
                'grip': 90,        # Open
                'grip_mouth': 90,
                'body_1': 90,      # Stand up
                'body_2': 90,      # Stand up
            },
            'reach': {
                'base': 90,
                'grip': 90,        # Open
                'grip_mouth': 90,
                'body_1': 135,     # Extend forward
                'body_2': 45,      # Lower joint
            },
            'grip_piece': {
                'base': 90,
                'grip': 30,        # Closed grip
                'grip_mouth': 30,  # Closed mouth
                'body_1': 135,
                'body_2': 45,
            },
            'lift': {
                'base': 90,
                'grip': 30,        # Keep closed
                'grip_mouth': 30,
                'body_1': 90,      # Lift up
                'body_2': 90,
            },
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
    
    def move_to_preset(self, preset_name):
        """Move to preset position with smart sequencing"""
        if preset_name not in self.presets:
            print(f"✗ Unknown preset. Available: {list(self.presets.keys())}\n")
            return
        
        print(f"\n→ Moving to '{preset_name}' position...")
        
        # Special sequence for FOLD: rotate base LEFT first
        if preset_name == 'fold':
            print("  Step 1: Rotating base LEFT for clearance...")
            base_ch = self.servo_map['base']
            self.safe_angle(base_ch, 0)
            time.sleep(0.5)
            
            print("  Step 2: Folding arm down...")
            for servo_name in ['body_1', 'body_2', 'grip', 'grip_mouth']:
                angle = self.presets[preset_name][servo_name]
                ch = self.servo_map[servo_name]
                self.safe_angle(ch, angle)
                time.sleep(0.1)
        
        # Special sequence for UNFOLD: extend arm first, then center base
        elif preset_name == 'unfold':
            print("  Step 1: Extending arm...")
            for servo_name in ['body_1', 'body_2', 'grip', 'grip_mouth']:
                angle = self.presets[preset_name][servo_name]
                ch = self.servo_map[servo_name]
                self.safe_angle(ch, angle)
                time.sleep(0.1)
            
            print("  Step 2: Centering base...")
            base_ch = self.servo_map['base']
            self.safe_angle(base_ch, 90)
            time.sleep(0.3)
        
        # Normal sequence for other presets
        else:
            for servo_name, angle in self.presets[preset_name].items():
                ch = self.servo_map[servo_name]
                self.safe_angle(ch, angle)
                time.sleep(0.1)
        
        print(f"✓ '{preset_name}' complete\n")
    
    def chess_move_sequence(self, rotate_degrees=45):
        """Execute a complete chess move: reach → grip → lift → rotate → place → release"""
        print("\n" + "="*50)
        print("CHESS MOVE SEQUENCE")
        print("="*50)
        
        # Step 1: Reach to piece
        print("\n[1/6] Reaching to piece...")
        self.move_to_preset('reach')
        time.sleep(0.5)
        
        # Step 2: Grip the piece
        print("\n[2/6] Gripping piece...")
        self.move_to_preset('grip_piece')
        time.sleep(0.5)
        
        # Step 3: Lift piece up
        print("\n[3/6] Lifting piece...")
        self.move_to_preset('lift')
        time.sleep(0.5)
        
        # Step 4: Rotate to destination
        print(f"\n[4/6] Rotating {rotate_degrees}° to destination...")
        base_ch = self.servo_map['base']
        current_angle = self.kit.servo[base_ch].angle
        new_angle = max(0, min(180, current_angle + rotate_degrees))
        self.safe_angle(base_ch, new_angle)
        time.sleep(0.8)
        
        # Step 5: Lower to place piece
        print("\n[5/6] Lowering to board...")
        self.move_to_preset('reach')
        time.sleep(0.5)
        
        # Step 6: Release piece
        print("\n[6/6] Releasing piece...")
        grip_ch = self.servo_map['grip']
        grip_mouth_ch = self.servo_map['grip_mouth']
        self.safe_angle(grip_ch, 90)
        self.safe_angle(grip_mouth_ch, 90)
        time.sleep(0.5)
        
        # Return to park
        print("\n[DONE] Returning to park...")
        self.move_to_preset('park')
        
        print("\n" + "="*50)
        print("✓ Chess move complete!")
        print("="*50 + "\n")
    
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
        print("  preset <name>      - Go to preset (fold/unfold/reach/park)")
        print("  list               - List all presets")
        print("  save <name>        - Save current position as preset")
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
                
                elif cmd[0] == 'preset' and len(cmd) == 2:
                    preset_name = cmd[1]
                    self.move_to_preset(preset_name)
                
                elif cmd[0] == 'list':
                    print("\nAvailable Presets:")
                    for name, positions in self.presets.items():
                        print(f"\n  {name}:")
                        for servo, angle in positions.items():
                            print(f"    {servo:12} → {angle}°")
                    print()
                
                elif cmd[0] == 'save' and len(cmd) == 2:
                    preset_name = cmd[1]
                    current_pos = {}
                    for servo_name, ch in self.servo_map.items():
                        try:
                            current_pos[servo_name] = int(self.kit.servo[ch].angle)
                        except:
                            current_pos[servo_name] = 90
                    self.presets[preset_name] = current_pos
                    print(f"✓ Saved current position as '{preset_name}'\n")
                
                elif cmd[0] == 'move':
                    rotate_deg = 45  # Default
                    if len(cmd) == 2:
                        rotate_deg = int(cmd[1])
                    self.chess_move_sequence(rotate_deg)
                
                elif cmd[0] == 'show':
                    print("\nCurrent Mapping:")
                    for name, ch in self.servo_map.items():
                        print(f"  {name:15} → Ch{ch}")
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