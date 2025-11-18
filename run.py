import subprocess
import os
import sys
from servo_control import move_to_square, pick_up_piece, release_piece, home_position

# Path to your robot_venv Python (Linux/RPi)
venv_python = os.path.expanduser('~/robot_venv/bin/python')

# Clear move history file
def clear_moves(file_path):
    try:
        with open(file_path, 'r+') as file:
            file.truncate(0)  # Clear the file
        print(f"Cleared {file_path}")
    except IOError as e:
        print(f"File I/O error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

clear_moves('save_move.txt')

# Paths to the repo scripts (adjust if needed)
script1 = 'gameProcessing.py'  # Backend/AI
script2 = 'GUI.py'  # User interface

# Start the two processes in parallel
print("Starting chess bot: AI backend + GUI...")
process1 = subprocess.Popen([venv_python, script1])
process2 = subprocess.Popen([venv_python, script2])

# Wait for both to finish
process1.wait()
process2.wait()

print("Game complete! Arm returning to home.")
home_position()  # Park the arm safely