import cv2
import chess
import numpy as np
from shared.utils import fen_to_grid, grid_to_fen

class VisionDetector:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.previous_fen = chess.Board().fen()
        self.square_size = 80  # Pixels per square (tune for your camera)

    def capture_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return None
        return frame

    def detect_grid(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # Edge detection for squares
        edges = cv2.Canny(gray, 50, 150)
        
        # Detect lines for board segmentation (horizontal/vertical)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=100, minLineLength=100, maxLineGap=10)
        
        # Extract horizontal and vertical lines for warp points
        horiz_lines = []
        vert_lines = []
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                if abs(y1 - y2) < 10:  # Horizontal
                    horiz_lines.append((min(x1, x2), y1, max(x1, x2), y2))
                if abs(x1 - x2) < 10:  # Vertical
                    vert_lines.append((x1, min(y1, y2), x2, max(y1, y2)))
        
        # Estimate 4 corners from lines (top-left, top-right, bottom-right, bottom-left)
        if len(horiz_lines) >= 2 and len(vert_lines) >= 2:
            top_h = min(h[1] for h in horiz_lines)
            bottom_h = max(h[3] for h in horiz_lines)
            left_v = min(v[0] for v in vert_lines)
            right_v = max(v[2] for v in vert_lines)
            src_points = np.float32([[left_v, top_h], [right_v, top_h], [right_v, bottom_h], [left_v, bottom_h]])
            # Target perfect square grid (8x8 ratio)
            dst_points = np.float32([[0, 0], [640, 0], [640, 640], [0, 640]])
            matrix = cv2.getPerspectiveTransform(src_points, dst_points)
            warped = cv2.warpPerspective(gray, matrix, (640, 640))
        else:
            warped = gray  # Fallback to original if lines not detected
        
        # Divide warped frame into 8x8 grid
        h, w = warped.shape
        grid = np.zeros((8, 8), dtype=bool)
        for row in range(8):
            for col in range(8):
                y = row * (h // 8)
                x = col * (w // 8)
                square = warped[y:y+(h//8), x:x+(w//8)]
                # Occupancy: mean brightness < 128 = piece present
                occupancy = np.mean(square) < 128
                grid[row, col] = occupancy
        return grid

    def infer_move(self):
        frame = self.capture_frame()
        if frame is None:
            return None
        current_grid = self.detect_grid(frame)
        current_fen = grid_to_fen(current_grid)  # Convert grid to FEN
        if current_fen == self.previous_fen:
            return None
        
        # Confidence calculation
        old_grid = fen_to_grid(self.previous_fen)
        diff = current_grid ^ old_grid
        num_changes = np.sum(diff)
        confidence = 0.0
        
        if num_changes == 2:  # Ideal: from and to
            confidence = 0.9  # High base for exact diff
            # Add piece match score (0.1 bonus if types match)
            from_candidates = np.where(diff)
            from_row, from_col = from_candidates[0][0], from_candidates[1][0]
            to_row, to_col = from_candidates[0][1], from_candidates[1][1]
            # Simple match: if occupancy flipped correctly (disappeared from, appeared to)
            if not current_grid[from_row, from_col] and current_grid[to_row, to_col]:
                confidence += 0.1
        elif num_changes == 1:
            confidence = 0.6  # Possible promotion/capture, but ambiguous
        else:
            confidence = 0.4  # Too many changes — noise or invalid
        
        if confidence < 0.8:
            print(f"DEBUG: Low confidence ({confidence:.2f}) — retrying scan")
            self.previous_fen = current_fen
            return None
        
        # Diff FEN to find move
        old_board = chess.Board(self.previous_fen)
        new_board = chess.Board(current_fen)
        for square in chess.SQUARES:
            if old_board.piece_at(square) and not new_board.piece_at(square):
                from_sq = chess.square_name(square)
                # Find matching piece in new board
                for to_square in chess.SQUARES:
                    if new_board.piece_at(to_square) == old_board.piece_at(square):
                        to_sq = chess.square_name(to_square)
                        move_uci = from_sq + to_sq
                        self.previous_fen = current_fen
                        print(f"DEBUG: Inferred move {move_uci} with confidence {confidence:.2f}")
                        return move_uci
        self.previous_fen = current_fen
        return None

    def close(self):
        self.cap.release()