from stockfish import Stockfish

STOCKFISH_PATH = '/opt/homebrew/bin/stockfish'  # Update path

def predict_move(fen):
    stockfish = Stockfish(path=STOCKFISH_PATH, parameters={
        "Threads": 4,
        "Hash": 256,
        "Skill Level": 10
    })
    stockfish.set_position(fen)
    best_move = stockfish.get_best_move()
    rationale = "This develops my position while challenging yours."  # Simple — expand with engine info
    return best_move, rationale