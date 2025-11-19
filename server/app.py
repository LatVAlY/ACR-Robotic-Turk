from flask import Flask, request, jsonify
from validation import validate_move
from ai import predict_move
import chess

app = Flask(__name__)

@app.route('/validate_and_predict', methods=['POST'])
def validate_and_predict():
    data = request.json
    uci = data.get('move', '')
    fen = data.get('fen', chess.Board().fen())
    
    board = chess.Board(fen)
    print(f"DEBUG: Server received user move: {uci}, initial FEN: {board.fen()}")
    
    valid, new_fen, explanation = validate_move(uci, fen)
    
    if valid:
        # AI prediction on isolated copy
        ai_board = chess.Board(new_fen)
        print(f"DEBUG: AI board FEN before Stockfish: {ai_board.fen()}")
        ai_uci, rationale = predict_move(ai_board.fen())
        if ai_uci:
            try:
                ai_move = chess.Move.from_uci(ai_uci)
                if ai_move in ai_board.legal_moves:
                    ai_board.push(ai_move)
                    explanation += f" AI counters with {ai_uci}: {rationale}"
                    game_over = ai_board.is_game_over()
                    print(f"DEBUG: AI move {ai_uci} valid, new FEN: {ai_board.fen()[:20]}...")
                else:
                    print(f"DEBUG: AI move {ai_uci} illegal — fallback random")
                    legal_moves = list(ai_board.legal_moves)
                    ai_uci = legal_moves[0].uci() if legal_moves else None
                    game_over = ai_board.is_game_over()
                    explanation += " AI adjusted to legal move."
            except ValueError as e:
                print(f"DEBUG: AI UCI parse error: {e} — fallback")
                legal_moves = list(ai_board.legal_moves)
                ai_uci = legal_moves[0].uci() if legal_moves else None
                game_over = ai_board.is_game_over()
                explanation += " AI selected safe alternative."
        else:
            game_over = ai_board.is_game_over()
            explanation += " AI passed — your advantage!"
    else:
        ai_uci = None
        game_over = board.is_game_over()
    
    return jsonify({
        'valid': valid,
        'ai_move': ai_uci,
        'fen': new_fen if valid else fen,
        'game_over': game_over,
        'explanation': explanation
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)