import cv2
import chess
import numpy as np
import sys
import os
from picamera2 import Picamera2  # Pi Camera backend

# Add parent directory to Python path to import shared module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.utils import fen_to_grid, grid_to_fen

class VisionMediaPipeDetector:
    def __init__(self):
        self.picam2 = Picamera2()
        self.picam2.configure(self.picam2.create_preview_configuration(main={"size": (640, 480)}))
        self.picam2.start()
        self.previous_fen = chess.Board().fen()
        self.square_size = 80  # Pixels per square
        self.scan_count = 0  # New: For debug logging

    def capture_frame(self):
        frame = self.picam2.capture_array()
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)  # OpenCV format

    def detect_grid(self, frame):
        print("DEBUG VISION: Capturing frame shape:", frame.shape)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=100, minLineLength=100, maxLineGap=10)
        print(f"DEBUG VISION: Found {len(lines) if lines is not None else 0} lines")
        
        horiz_lines = []
        vert_lines = []
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                if abs(y1 - y2) < 10:
                    horiz_lines.append((min(x1, x2), y1, max(x1, x2), y2))
                if abs(x1 - x2) < 10:
                    vert_lines.append((x1, min(y1, y2), x2, max(y1, y2)))
        
        print(f"DEBUG VISION: Horiz lines: {len(horiz_lines)}, Vert lines: {len(vert_lines)}")
        
        if len(horiz_lines) >= 2 and len(vert_lines) >= 2:
            top_h = min(h[1] for h in horiz_lines)
            bottom_h = max(h[3] for h in horiz_lines)
            left_v = min(v[0] for v in vert_lines)
            right_v = max(v[2] for v in vert_lines)
            print(f"DEBUG VISION: Board bounds - Top: {top_h}, Bottom: {bottom_h}, Left: {left_v}, Right: {right_v}")
            src_points = np.float32([[left_v, top_h], [right_v, top_h], [right_v, bottom_h], [left_v, bottom_h]])
            dst_points = np.float32([[0, 0], [640, 0], [640, 640], [0, 640]])
            matrix = cv2.getPerspectiveTransform(src_points, dst_points)
            warped = cv2.warpPerspective(gray, matrix, (640, 640))
            print("DEBUG VISION: Perspective warp successful")
        else:
            print("DEBUG VISION: Insufficient lines for warp - using raw gray")
            warped = gray
            # Fallback: Assume centered board, crop roughly
            h, w = warped.shape
            board_h = min(h, w) // 8 * 8
            start = (h - board_h) // 2 if h > w else 0
            warped = warped[start:start+board_h, :board_h] if h > w else warped[:board_h, start:start+board_h]
            print(f"DEBUG VISION: Fallback crop to {warped.shape}")
        
        h, w = warped.shape
        grid = np.zeros((8, 8), dtype=bool)
        occupancy_stats = []  # New: Track mean per square for debug
        for row in range(8):
            for col in range(8):
                y = row * (h // 8)
                x = col * (w // 8)
                square = warped[y:y+(h//8), x:x+(w//8)]
                mean_val = np.mean(square)
                occupancy = mean_val < 128  # Assumes dark pieces; tune threshold if light/dark board
                grid[row, col] = occupancy
                occupancy_stats.append((row, col, mean_val, occupancy))
                print(f"DEBUG VISION: Square r{row}c{col}: mean={mean_val:.1f}, occupied={occupancy}")
        
        print("DEBUG VISION: Full occupancy grid:\n", grid)  # Bool array print
        # New: Print occupancy stats summary
        dark_squares = sum(1 for s in occupancy_stats if s[2] < 128)
        print(f"DEBUG VISION: Total dark squares detected: {dark_squares}/64")
        return grid

    def infer_move(self):
        self.scan_count += 1
        print(f"\n=== VISION SCAN #{self.scan_count} ===")
        frame = self.capture_frame()
        if frame is None:
            print("DEBUG VISION: No frame captured")
            return None
        
        current_grid = self.detect_grid(frame)
        current_fen = grid_to_fen(current_grid)
        print(f"DEBUG VISION: Current FEN: {current_fen}")
        print("DEBUG VISION: Previous FEN: ", self.previous_fen)
        
        if current_fen == self.previous_fen:
            print("DEBUG VISION: No board change — skipping inference")
            # Still update to avoid drift, but no move
            self.previous_fen = current_fen
            return (None, None, None, 0.0)  # Full tuple for client unpack
        
        old_grid = fen_to_grid(self.previous_fen)
        print("DEBUG VISION: Old grid:\n", old_grid)
        print("DEBUG VISION: Current grid:\n", current_grid)
        
        diff = current_grid ^ old_grid
        print("DEBUG VISION: Diff grid (changes):\n", diff)
        num_changes = np.sum(diff)
        print(f"DEBUG VISION: Num changes: {num_changes}")
        
        move_conf = 0.0
        move_uci = None
        
        if num_changes == 2:
            move_conf = 0.9
            # Find from/to: Assume from is now empty (was occupied), to is now occupied (was empty)
            from_candidates = np.where((old_grid & ~current_grid) | (~old_grid & current_grid))
            if len(from_candidates[0]) == 2:
                # Sort by rows/cols to identify from/to
                rows, cols = from_candidates[0], from_candidates[1]
                idx = np.argsort(rows * 8 + cols)  # Flatten to sort positions
                from_row, from_col = rows[idx[0]], cols[idx[0]]
                to_row, to_col = rows[idx[1]], cols[idx[1]]
                # Confirm direction: from occupied to empty
                if old_grid[from_row, from_col] and not current_grid[from_row, from_col] and \
                   not old_grid[to_row, to_col] and current_grid[to_row, to_col]:
                    from_square = chess.square(from_col, 7 - from_row)  # Chess: row 0=8 (top), col 0=a
                    to_square = chess.square(to_col, 7 - to_row)
                    move_uci = chess.square_name(from_square) + chess.square_name(to_square)
                    print(f"DEBUG VISION: Candidate from {chess.square_name(from_square)} (r{from_row}c{from_col}), to {chess.square_name(to_square)} (r{to_row}c{to_col})")
                    # Validate as legal move? Optional, but boosts conf
                    temp_board = chess.Board(self.previous_fen)
                    if chess.Move.from_uci(move_uci) in temp_board.legal_moves:
                        move_conf += 0.1
                    else:
                        print("DEBUG VISION: Invalid legal move — lowering conf")
                        move_conf -= 0.2
                else:
                    print("DEBUG VISION: Diff pattern doesn't match from->to")
                    move_conf = 0.0
            else:
                print("DEBUG VISION: Unexpected diff positions")
        elif num_changes > 2:
            print("DEBUG VISION: Too many changes ({num_changes}) — possible capture or multi-move, ignoring")
            # Could handle captures: 3 changes (from empty, to occupied, capture square empty)
            # But for now, low conf
            move_conf = 0.3
        else:
            print("DEBUG VISION: Too few changes ({num_changes}) — no move")
        
        print(f"DEBUG VISION: Final move_uci='{move_uci}', conf={move_conf:.2f}")
        
        if move_conf < 0.8:
            print("DEBUG VISION: Low confidence — not returning move")
            self.previous_fen = current_fen
            return (None, None, None, move_conf)
        
        self.previous_fen = current_fen
        print(f"DEBUG VISION: Returning inferred move {move_uci} with conf {move_conf:.2f}")
        return (move_uci, None, None, move_conf)  # Full tuple: move_uci, gesture, expression, conf (float)

    def close(self):
        self.picam2.stop()
        print("DEBUG VISION: Camera stopped")