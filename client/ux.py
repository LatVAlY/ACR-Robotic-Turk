import subprocess
import time

class UXHandler:
    def __init__(self):
        self.current_status = 'idle'
        
    def speak(self, text):
        subprocess.run(['espeak', text])
    
    def feedback_move_valid(self, move):
        self.speak(f"Your move {move} is valid — my turn.")
        self.current_status = 'waiting'
    
    def feedback_invalid(self, explanation):
        self.speak(f"Invalid move: {explanation}. Try again.")
        self.current_status = 'scanning'
        time.sleep(2)
    
    def feedback_ai_move(self, ai_move):
        from_sq, to_sq = ai_move[:2], ai_move[2:]
        self.speak(f"Playing {from_sq} to {to_sq}.")
        self.current_status = 'executing'
    
    def game_over(self, winner):
        self.speak(f"Game over. {winner} wins! Good game.")
        self.current_status = 'idle'