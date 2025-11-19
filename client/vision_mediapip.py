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
        self.previous_grid = None  # Raw grid for diff (initial sync)
        self.previous_fen = chess.Board().fen()  # For chess validation only
        self.square_size = 80  # Pixels per square
        self.scan_count = 0  # For debug logging
        self.baseline_scans = 5  # First 5 scans sync without move

    def capture_frame(self):
        frame = self.picam2.capture_array()
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)  # OpenCV format

    def detect_grid(self, frame):
        print("DEBUG VISION: Capturing frame shape:", frame.shape)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Pre-process for better edges - Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 30, 100)  # Lowered thresholds for more edges
        
        # Use probabilistic Hough for better line detection
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=30, minLineLength=30, maxLineGap=20)  # Lowered for more lines
        print(f"DEBUG VISION: Found {len(lines) if lines is not None else 0} lines")
        
        horiz_lines = []
        vert_lines = []
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                if abs(y1 - y2) < 10:  # Horizontal
                    horiz_lines.append((min(x1, x2), y1, max(x1, x2), y2))
                if abs(x1 - x2) < 10:  # Vertical
                    vert_lines.append((x1, min(y1, y2), x2, max(y1, y2)))
        
        print(f"DEBUG VISION: Horiz lines: {len(horiz_lines)}, Vert lines: {len(vert_lines)}")
        
        warped = None
        if len(horiz_lines) >= 4 and len(vert_lines) >= 4:  # Need more lines for 8x8
            # Sort and select top/bottom/left/right
            horiz_lines.sort(key=lambda h: h[1])  # By y
            vert_lines.sort(key=lambda v: v[0])    # By x
            top_h = horiz_lines[0][1]
            bottom_h = horiz_lines[-1][3]
            left_v = vert_lines[0][0]
            right_v = vert_lines[-1][2]
            print(f"DEBUG VISION: Board bounds - Top: {top_h}, Bottom: {bottom_h}, Left: {left_v}, Right: {right_v}")
            
            # Ensure bounds make sense
            h_board = bottom_h - top_h
            w_board = right_v - left_v
            if 0 < h_board < frame.shape[0] and 0 < w_board < frame.shape[1]:
                src_points = np.float32([[left_v, top_h], [right_v, top_h], [right_v, bottom_h], [left_v, bottom_h]])
                dst_points = np.float32([[0, 0], [w_board, 0], [w_board, h_board], [0, h_board]])
                matrix = cv2.getPerspectiveTransform(src_points, dst_points)
                warped = cv2.warpPerspective(gray, matrix, (int(w_board), int(h_board)))
                print(f"DEBUG VISION: Perspective warp to {warped.shape}")
            else:
                print("DEBUG VISION: Invalid bounds - fallback")
        else:
            print("DEBUG VISION: Insufficient lines - trying contour detection for board")
            # Contour-based board detection as fallback
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                # Find largest quadrilateral contour (approx board)
                largest_contour = max(contours, key=cv2.contourArea)
                epsilon = 0.02 * cv2.arcLength(largest_contour, True)
                approx = cv2.approxPolyDP(largest_contour, epsilon, True)
                if len(approx) == 4:
                    src_points = approx.reshape(4, 2).astype(np.float32)
                    dst_points = np.float32([[0, 0], [640, 0], [640, 640], [0, 640]])
                    matrix = cv2.getPerspectiveTransform(src_points, dst_points)
                    warped = cv2.warpPerspective(gray, matrix, (640, 640))
                    print("DEBUG VISION: Contour warp successful")
                else:
                    print("DEBUG VISION: No quad contour - raw fallback")
        
        if warped is None:
            print("DEBUG VISION: Using raw gray fallback")
            warped = gray
            h, w = warped.shape
            # Improved fallback: Crop to square, center board
            size = min(h, w)
            start_y = (h - size) // 2
            start_x = (w - size) // 2
            warped = warped[start_y:start_y + size, start_x:start_x + size]
            print(f"DEBUG VISION: Centered crop to {warped.shape}")
        
        h, w = warped.shape
        grid = np.zeros((8, 8), dtype=bool)
        occupancy_stats = []
        for row in range(8):
            for col in range(8):
                y_start = row * (h // 8)
                y_end = y_start + (h // 8)
                x_start = col * (w // 8)
                x_end = x_start + (w // 8)
                square = warped[y_start:y_end, x_start:x_end]
                
                # Adaptive threshold with Otsu for better occupancy (edges/darkness)
                if square.size > 0:
                    _, thresh = cv2.threshold(square, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    dark_ratio = np.sum(thresh == 0) / thresh.size  # Fraction dark pixels
                    mean_val = np.mean(square)
                else:
                    dark_ratio = 0.5
                    mean_val = 128
                
                # Stricter occupancy: dark_ratio >0.7 AND mean <60 (for true pieces)
                occupancy = (dark_ratio > 0.7) and (mean_val < 60)
                grid[row, col] = occupancy
                occupancy_stats.append((row, col, mean_val, dark_ratio, occupancy))
                print(f"DEBUG VISION: Square r{row}c{col}: mean={mean_val:.1f}, dark_ratio={dark_ratio:.2f}, occupied={occupancy}")
        
        print("DEBUG VISION: Full occupancy grid:\n", grid)
        occupied_count = np.sum(grid)
        print(f"DEBUG VISION: Total occupied squares: {occupied_count}/64")
        return grid

    def infer_move(self):
        self.scan_count += 1
        print(f"\n=== VISION SCAN #{self.scan_count} ===")
        frame = self.capture_frame()
        if frame is None:
            print("DEBUG VISION: No frame captured")
            return (None, None, None, 0.0)
        
        current_grid = self.detect_grid(frame)
        
        # Baseline sync for first scans
        if self.scan_count <= self.baseline_scans:
            print("DEBUG VISION: Baseline scan — setting previous grid and FEN")
            self.previous_grid = current_grid.copy()
            self.previous_fen = grid_to_fen(current_grid)
            return (None, None, None, 0.0)
        
        # Grid diff for changes (raw occupancy)
        diff = current_grid ^ self.previous_grid
        print("DEBUG VISION: Diff grid (changes):\n", diff)
        num_changes = np.sum(diff)
        print(f"DEBUG VISION: Num changes: {num_changes}")
        
        move_conf = 0.0
        move_uci = None
        change_positions = np.where(diff)
        
        if num_changes == 0:
            print("DEBUG VISION: No changes — skipping")
            return (None, None, None, 0.0)
        elif num_changes == 2:
            # Single move
            rows, cols = change_positions
            from_idx = 0 if self.previous_grid[rows[0], cols[0]] else 1
            to_idx = 1 - from_idx
            from_row, from_col = rows[from_idx], cols[from_idx]
            to_row, to_col = rows[to_idx], cols[to_idx]
            if self.previous_grid[from_row, from_col] and not current_grid[from_row, from_col] and \
               not self.previous_grid[to_row, to_col] and current_grid[to_row, to_col]:
                from_square = chess.square(from_col, 7 - from_row)
                to_square = chess.square(to_col, 7 - to_row)
                move_uci = chess.square_name(from_square) + chess.square_name(to_square)
                move_conf = 0.9
                # Legal check on FEN
                temp_board = chess.Board(self.previous_fen)
                if chess.Move.from_uci(move_uci) in temp_board.legal_moves:
                    move_conf += 0.1
                print(f"DEBUG VISION: Inferred single move {move_uci}")
            else:
                print("DEBUG VISION: Diff not from->to pattern")
        elif 2 < num_changes <= 4:
            print("DEBUG VISION: Multi-change (possible capture) — skipping for now")
            move_conf = 0.6
        else:
            print(f"DEBUG VISION: Too many changes ({num_changes}) — forcing sync")
            move_conf = 0.0
        
        print(f"DEBUG VISION: Final move_uci='{move_uci}', conf={move_conf:.2f}")
        
        # Periodic full sync
        if self.scan_count % 3 == 0 or num_changes > 4:
            print("DEBUG VISION: Periodic sync — updating previous")
            self.previous_grid = current_grid.copy()
            self.previous_fen = grid_to_fen(current_grid)
            sync_conf = 0.7 if num_changes < 10 else 0.4
            return (None, None, None, sync_conf)
        
        if move_conf < 0.6:
            print("DEBUG VISION: Low confidence — updating previous but no move")
            self.previous_grid = current_grid.copy()
            self.previous_fen = grid_to_fen(current_grid)
            return (None, None, None, move_conf)
        
        self.previous_grid = current_grid.copy()
        self.previous_fen = grid_to_fen(current_grid)
        print(f"DEBUG VISION: Returning inferred move {move_uci} with conf {move_conf:.2f}")
        return (move_uci, None, None, move_conf)  # Full tuple

    def close(self):
        self.picam2.stop()
        print("DEBUG VISION: Camera stopped")