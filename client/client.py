import time
import chess
import requests
import sys
import os

# Add parent directory to Python path to import shared module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motion import MotionController
from ux import UXHandler
from vision_mediapip import VisionMediaPipeDetector
from shared.utils import load_json

# Use path relative to project root
config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'shared', 'config.json')
SERVER_URL = load_json(config_path)['server_url']
BOARD = chess.Board()

class ChessBotClient:
    def __init__(self):
        self.vision = VisionMediaPipeDetector()
        self.motion = MotionController()
        self.ux = UXHandler()
        self.game_active = True
        self.retry_count = 0
        self.max_retries = 3
        
    def send_to_server(self, move_uci):
        payload = {'move': move_uci, 'fen': BOARD.fen()}
        try:
            response = requests.post(f'{SERVER_URL}/validate_and_predict', json=payload, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data
            else:
                print(f"Server error: {response.status_code}")
                return {'valid': False, 'error': 'Server unavailable', 'explanation': 'Check connection'}
        except requests.exceptions.RequestException as e:
            print(f"Network error: {e}")
            return {'valid': False, 'error': 'Network issue', 'explanation': 'Retrying...'}
    
    def handle_move(self, move_uci):
        data = self.send_to_server(move_uci)
        if data['valid']:
            self.ux.feedback_move_valid(move_uci)
            BOARD.push(chess.Move.from_uci(move_uci))
            ai_move = data['ai_move']
            if ai_move:
                self.ux.feedback_ai_move(ai_move)
                from_sq, to_sq = ai_move[:2], ai_move[2:]
                success = self.motion.execute_move(from_sq, to_sq)
                if success:
                    BOARD.push(chess.Move.from_uci(ai_move))
                else:
                    self.ux.speak("Motion failed — retrying next turn.")
            if data['game_over']:
                winner = 'White' if BOARD.result() == '0-1' else 'Black'
                self.ux.game_over(winner)
                self.game_active = False
        else:
            self.ux.feedback_invalid(data['explanation'])
            self.retry_count += 1
            if self.retry_count >= self.max_retries:
                self.ux.speak("Too many errors — resetting game.")
                self.reset_game()
                self.retry_count = 0
    
    def reset_game(self):
        global BOARD
        BOARD = chess.Board()
        self.motion.home_position()
        self.ux.speak("Game reset — your turn.")
    
    def run_loop(self):
        self.ux.speak("Game started — watching for your move.")
        self.motion.home_position()
        
        while self.game_active:
            result = self.vision.infer_move()
            if result is None:
                print("DEBUG: No move detected (low confidence) — scanning...")
                time.sleep(2)
                continue
            
            move_uci, gesture, expression, conf = result
            conf_float = float(conf) if conf is not None else 0.0  # Fix: Convert str to float safely
            if move_uci and conf_float >= 0.8:
                print(f"DEBUG: Detected move {move_uci} (conf {conf_float:.2f}, gesture {gesture}, expr {expression})")
                self.handle_move(move_uci)
                if gesture == 'wave':
                    self.motion.home_position()  # Pause for wave response
                    self.ux.speak("Wave received — hello!")
                if expression == 'frown':
                    self.ux.speak("Tough move? Keep going — you're improving!")
            time.sleep(2)  # Scan interval
        
        self.vision.close()
        self.motion.home_position()

if __name__ == '__main__':
    bot = ChessBotClient()
    bot.run_loop()