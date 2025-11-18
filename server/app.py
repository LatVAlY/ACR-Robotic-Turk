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
    
    valid, new_fen, explanation = validate_move(uci, fen)
    
    if valid:
        ai_uci, rationale = predict_move(new_fen)
        explanation += f" AI counters with {ai_uci}: {rationale}"
        game_over = chess.Board(new_fen).is_game_over()
        return jsonify({
            'valid': True,
            'ai_move': ai_uci,
            'fen': new_fen,
            'game_over': game_over,
            'explanation': explanation
        })
    else:
        return jsonify({
            'valid': False,
            'ai_move': None,
            'fen': fen,
            'game_over': False,
            'explanation': explanation
        }), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)