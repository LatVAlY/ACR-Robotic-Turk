from servo_control import kit
import json

print("Manual calibration: Position arm over square, press Enter to save.")
squares = ['a1', 'e4', 'h8']  # Test first
movements = {}

for square in squares:
    print(f"\nHover gripper over {square} (1cm above). Press Enter...")
    input()
    angles = [kit.servo[i].angle for i in range(3)]
    movements[square] = angles
    print(f"Saved {square}: {angles}")

with open('controlMovements.json', 'w') as f:
    json.dump(movements, f, indent=4)
print("JSON updated! Add all 64 squares.")