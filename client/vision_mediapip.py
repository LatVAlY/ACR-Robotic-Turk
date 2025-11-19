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

    def capture_frame(self):
        frame = self.picam2.capture_array()
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)  # OpenCV format

    def detect_grid(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=100, minLineLength=100, maxLineGap=10)
        
        horiz_lines = []
        vert_lines = []
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                if abs(y1 - y2) < 10:
                    horiz_lines.append((min(x1, x2), y1, max(x1, x2), y2))
                if abs(x1 - x2) < 10:
                    vert_lines.append((x1, min(y1, y2), x2, max(y1, y2)))
        
        if len(horiz_lines) >= 2 and len(vert_lines) >= 2:
            top_h = min(h[1] for h in horiz_lines)
            bottom_h = max(h[3] for h in horiz_lines)
            left_v = min(v[0] for v in vert_lines)
            right_v = max(v[2] for v in vert_lines)
            src_points = np.float32([[left_v, top_h], [right_v, top_h], [right_v, bottom_h], [left_v, bottom_h]])
            dst_points = np.float32([[0, 0], [640, 0], [640, 640], [0, 640]])
            matrix = cv2.getPerspectiveTransform(src_points, dst_points)
            warped = cv2.warpPerspective(gray, matrix, (640, 640))
        else:
            warped = gray
        
        h, w = warped.shape
        grid = np.zeros((8, 8), dtype=bool)
        for row in range(8):
            for col in range(8):
                y = row * (h // 8)
                x = col * (w // 8)
                square = warped[y:y+(h//8), x:x+(w//8)]
                occupancy = np.mean(square) < 128
                grid[row, col] = occupancy
        return grid

    def infer_move(self):
        frame = self.capture_frame()
        if frame is None:
            return None
        current_grid = self.detect_grid(frame)
        current_fen = grid_to_fen(current_grid)
        if current_fen == self.previous_fen:
            return None
        
        old_grid = fen_to_grid(self.previous_fen)
        diff = current_grid ^ old_grid
        num_changes = np.sum(diff)
        move_conf = 0.0
        move_uci = None
        
        if num_changes == 2:
            move_conf = 0.9
            from_candidates = np.where(diff)
            from_row, from_col = from_candidates[0][0], from_candidates[1][0]
            to_row, to_col = from_candidates[0][1], from_candidates[1][1]
            from_square = chess.square(from_col, 7 - from_row)
            to_square = chess.square(to_col, 7 - to_row)
            move_uci = chess.square_name(from_square) + chess.square_name(to_square)
            if not current_grid[from_row, from_col] and current_grid[to_row, to_col]:
                move_conf += 0.1
        
        if move_conf < 0.8:
            print(f"DEBUG: Low confidence ({move_conf:.2f}) — retrying scan")
            self.previous_fen = current_fen
            return None
        
        self.previous_fen = current_fen
        print(f"DEBUG: Inferred move {move_uci} with confidence {move_conf:.2f}")
        return move_uci

    def close(self):
        self.picam2.stop()