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
        
        # Deblur & Enhance: Bilateral filter + CLAHE for low-light contrast
        deblurred = cv2.bilateralFilter(gray, 9, 75, 75)  # Preserves edges, reduces blur
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(deblurred)
        blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)  # Still blur for edges
        
        # Edges: Canny on enhanced + Sobel vert
        edges = cv2.Canny(blurred, 50, 150)
        sobelx = cv2.Sobel(blurred, cv2.CV_64F, 1, 0, ksize=3)
        sobelx = cv2.convertScaleAbs(sobelx)
        edges_vert = cv2.Canny(sobelx, 50, 150)
        
        # Hough: Tighter params for blurry lines
        lines_h = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=40, minLineLength=60, maxLineGap=15)
        lines_v = cv2.HoughLinesP(edges_vert, 1, np.pi / 180, threshold=40, minLineLength=60, maxLineGap=15)
        
        horiz_lines = []
        vert_lines = []
        if lines_h is not None:
            for line in lines_h:
                x1, y1, x2, y2 = line[0]
                if abs(y1 - y2) < 15:  # Looser angle tol for tilt
                    horiz_lines.append((min(x1, x2), y1, max(x1, x2), y2))
        if lines_v is not None:
            for line in lines_v:
                x1, y1, x2, y2 = line[0]
                if abs(x1 - x2) < 15:
                    vert_lines.append((x1, min(y1, y2), x2, max(y1, y2)))
        
        print(f"DEBUG VISION: Horiz lines: {len(horiz_lines)}, Vert lines: {len(vert_lines)}")
        
        warped = None
        if len(horiz_lines) >= 4 and len(vert_lines) >= 4:
            # Improved clustering: Aim for 9 lines, with wider gap tol for blur
            def cluster_lines(lines, is_horiz=True, num_target=9):
                if not lines: return []
                coords = [l[1] if is_horiz else l[0] for l in lines]
                coords = sorted(set(coords))
                clusters = []
                current = [coords[0]]
                for coord in coords[1:]:
                    if abs(coord - current[-1]) < 30:  # Wider for broken lines
                        current.append(coord)
                    else:
                        clusters.append(np.mean(current))
                        current = [coord]
                clusters.append(np.mean(current))
                # Select/Interpolate to ~num_target
                if len(clusters) < num_target:
                    # Simple interpolate if short
                    step_h = (clusters[-1] - clusters[0]) / (num_target - 1)
                    clusters = [clusters[0] + i * step_h for i in range(num_target)]
                return sorted(clusters[:num_target])
            
            h_clusters = cluster_lines(horiz_lines, True)
            v_clusters = cluster_lines(vert_lines, False)
            
            if len(h_clusters) >= 8 and len(v_clusters) >= 8:
                top_h, bottom_h = h_clusters[0], h_clusters[-1]
                left_v, right_v = v_clusters[0], v_clusters[-1]
                h_board = bottom_h - top_h
                w_board = right_v - left_v
                if 100 < h_board < frame.shape[0]-100 and 100 < w_board < frame.shape[1]-100:  # Bounds check
                    src_points = np.float32([[left_v, top_h], [right_v, top_h], [right_v, bottom_h], [left_v, bottom_h]])
                    dst_points = np.float32([[0, 0], [512, 0], [512, 512], [0, 512]])  # Fixed square
                    matrix = cv2.getPerspectiveTransform(src_points, dst_points)
                    warped = cv2.warpPerspective(enhanced, matrix, (512, 512))  # Use enhanced
                    print(f"DEBUG VISION: Clustered warp to {warped.shape}")
        
        # Fallback: Enhanced contour
        if warped is None:
            print("DEBUG VISION: Fallback to contour on enhanced")
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                largest = max(contours, key=cv2.contourArea)
                epsilon = 0.06 * cv2.arcLength(largest, True)  # Even looser for blur
                approx = cv2.approxPolyDP(largest, epsilon, True)
                if len(approx) >= 4:  # Accept near-quad
                    src_points = approx.reshape(-1, 2).astype(np.float32)[:4]  # Take first 4
                    dst_points = np.float32([[0, 0], [512, 0], [512, 512], [0, 512]])
                    matrix = cv2.getPerspectiveTransform(src_points, dst_points)
                    warped = cv2.warpPerspective(enhanced, matrix, (512, 512))
                    print("DEBUG VISION: Contour warp successful")
        
        if warped is None:
            print("DEBUG VISION: Raw fallback on enhanced")
            h, w = enhanced.shape
            size = min(h, w)
            start_y, start_x = (h - size) // 2, (w - size) // 2
            warped = enhanced[start_y:start_y + size, start_x:start_x + size]
            print(f"DEBUG VISION: Centered crop to {warped.shape}")
        
        # Dynamic square_size
        h, w = warped.shape
        square_size = min(h // 8, w // 8)
        self.square_size = square_size
        grid = np.zeros((8, 8), dtype=bool)
        
        for row in range(8):
            for col in range(8):
                y_start = row * (h // 8)
                y_end = (row + 1) * (h // 8)
                x_start = col * (w // 8)
                x_end = (col + 1) * (w // 8)
                square = warped[y_start:y_end, x_start:x_end]
                
                if square.size > 0:
                    # Adaptive thresh + stronger morph for blur
                    thresh = cv2.adaptiveThreshold(square, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 3)
                    kernel = np.ones((2,2), np.uint8)  # Smaller for fine details
                    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
                    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)  # Remove noise
                    dark_ratio = np.sum(thresh == 0) / thresh.size
                    mean_val = np.mean(square)
                    
                    # Further relaxed + variance check (pieces have texture variance > empties)
                    var_val = np.var(square)
                    occupancy = (dark_ratio > 0.55) and (mean_val < 90) and (var_val > 200)  # Tune var for plastic texture
                else:
                    dark_ratio, mean_val, var_val = 0.5, 128, 0
                    occupancy = False
                
                grid[row, col] = occupancy
                print(f"DEBUG VISION: Square r{row}c{col}: mean={mean_val:.1f}, dark={dark_ratio:.2f}, var={var_val:.0f}, occ={occupancy}")
        
        # Quick validation: Flip if upside-down (check occupied rows)
        occupied_rows = np.sum(grid, axis=1)
        if occupied_rows[0] > occupied_rows[7]:  # Black on top?
            grid = np.flipud(grid)
            print("DEBUG VISION: Auto-flipped grid for white-at-bottom")
        
        print("DEBUG VISION: Full grid:\n", grid)
        occupied_count = np.sum(grid)
        print(f"DEBUG VISION: Total occupied: {occupied_count}/64")
        
        # Save warped for debug (optional, comment if not needed)
        cv2.imwrite(f'warped_scan{self.scan_count}.jpg', warped)
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