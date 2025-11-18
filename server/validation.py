import chess
# TODO later everything will be returned back to AI, Only AI can generate reason (text, description to talk)
def validate_move(uci, fen):
    board = chess.Board(fen)
    try:
        move = chess.Move.from_uci(uci)
        if move in board.legal_moves:
            board.push(move)
            return True, board.fen(), "Move accepted — strategic choice!"
        else:
            reason = get_illegal_reason(board, move)
            return False, board.fen(), f"Invalid: {reason}"
    except ValueError:
        return False, fen, "Invalid UCI format — use 'e2e4' style."

def get_illegal_reason(board, move):
    if move not in board.legal_moves:
        # Simple rule check
        piece = board.piece_at(move.from_square)
        if piece and piece.piece_type == chess.PAWN:
            if move.to_square < move.from_square and piece.color == chess.WHITE:
                return "Pawns can't retreat — advance only."
        return "Blocked path or illegal for piece type."
    return "Unknown error."