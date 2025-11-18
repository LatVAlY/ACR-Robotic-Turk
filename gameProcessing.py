import chess
import numpy as np  # Already installed
from art import tprint  # Already installed
# Other imports...

print("DEBUG: Starting gameProcessing.py")

# Main board setup
board = chess.Board()
print("DEBUG: Board created")

tprint("CHESS")  # Your ASCII art
print("DEBUG: ASCII art printed")

# Game loop (this is where it's likely stuck)
while not board.is_game_over():
    print("DEBUG: Top of game loop")
    
    # User move input
    print("DEBUG: Waiting for user move...")
    user_move = input("Your move (e.g., e2 e4): ").strip()
    print(f"DEBUG: User entered: '{user_move}'")
    
    if user_move:
        try:
            # Parse move
            move = board.parse_san(user_move)  # Or board.parse_uci(user_move)
            print(f"DEBUG: Parsed move: {move}")
            board.push(move)
            print("DEBUG: User move applied")
        except Exception as e:
            print(f"DEBUG: Move parse error: {e}")
            continue
    else:
        print("DEBUG: Empty input, skipping")
    
    # AI move
    print("DEBUG: Calculating AI move...")
    best_move = your_ai_function(board)  # Replace with your minimax call
    print(f"DEBUG: AI chose: {best_move}")
    
    board.push(best_move)
    print("DEBUG: AI move applied")
    
    # Arm move (your integration)
    print("DEBUG: Calling arm move...")
    from_square = best_move.uci()[:2]
    to_square = best_move.uci()[2:]
    home_position()
    move_to_square(from_square)
    pick_up_piece()
    move_to_square(to_square)
    release_piece()
    home_position()
    print("DEBUG: Arm move complete")
    
    # Print board
    print("DEBUG: Printing board...")
    print(board)  # Or your ASCII print
    print("DEBUG: Bottom of loop")

print("DEBUG: Game over")