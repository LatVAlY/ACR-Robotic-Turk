import json
import chess

def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)

def fen_to_grid(fen):
    board = chess.Board(fen)
    grid = np.zeros((8, 8), dtype=bool)
    for square in chess.SQUARES:
        row, col = chess.square_rank(square), chess.square_file(square)
        grid[row, col] = board.piece_at(square) is not None
    return grid

def grid_to_fen(grid):
    # Reverse: Grid to FEN (placeholder — use chess.Board.set_piece_map)
    board = chess.Board()
    for r in range(8):
        for c in range(8):
            square = chess.square(c, r)
            if grid[r, c]:
                board.set_piece_at(square, chess.Piece(chess.PAWN, chess.WHITE))  # Default pawn — expand
    return board.fen()

def fen_diff_to_uci(old_fen, new_fen):
    old_board = chess.Board(old_fen)
    new_board = chess.Board(new_fen)
    for square in chess.SQUARES:
        if old_board.piece_at(square) and not new_board.piece_at(square):
            from_sq = chess.square_name(square)
            # Find matching piece in new
            for to_square in chess.SQUARES:
                if new_board.piece_at(to_square) == old_board.piece_at(square):
                    to_sq = chess.square_name(to_square)
                    return from_sq + to_sq
    return None