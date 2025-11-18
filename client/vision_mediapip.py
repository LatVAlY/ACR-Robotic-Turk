import cv2
import chess
import numpy as np
import mediapipe as mp
from shared.utils import fen_to_grid, grid_to_fen

class VisionMediaPipeDetector:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.previous_fen = chess.Board().fen()
        self.square_size = 80
        
        # MediaPipe setup
        self.mp_hands = mp.solutions.hands
        self.mp_face = mp.solutions.face_mesh
        self.hands = self.mp_hands.Hands(static_image_mode=False, max_num_hands=2, min_detection_confidence=0.7)
        self.face = self.mp_face.FaceMesh(static_image_mode=False, max_num_faces=1, min_detection_confidence=0.7)
        self.mp_draw = mp.solutions.drawing_utils
        
    def capture_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return None
        return frame

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

    def detect_gestures(self, frame):
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        hand_results = self.hands.process(rgb_frame)
        gesture = 'none'
        confidence = 0.0
        
        if hand_results.multi_hand_landmarks:
            for hand_landmarks in hand_results.multi_hand_landmarks:
                self.mp_draw.draw_landmarks(frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
                # Handshake/wave: Check palm open (fingers spread)
                if len(hand_landmarks.landmark) > 0:
                    finger_tips = [4, 8, 12, 16, 20]  # Thumb, index, middle, ring, pinky tips
                    palm_base = hand_landmarks.landmark[0].y
                    spread = sum(hand_landmarks.landmark[tip].y < palm_base for tip in finger_tips)
                    if spread >= 4:  # Open palm
                        # Wave: Velocity in x (left-right sweep)
                        # Assume previous x (track in state)
                        current_x = hand_landmarks.landmark[0].x
                        if 'prev_x' in self.__dict__ and abs(current_x - self.prev_x) > 0.05:
                            gesture = 'wave'
                            confidence = 0.8
                        self.prev_x = current_x
        
        return gesture, confidence

    def detect_expression(self, frame):
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_results = self.face.process(rgb_frame)
        expression = 'neutral'
        confidence = 0.0
        
        if face_results.multi_face_landmarks:
            for face_landmarks in face_results.multi_face_landmarks:
                self.mp_draw.draw_landmarks(frame, face_landmarks, self.mp_face.FACEMESH_CONTOURS)
                # Frown: Mouth corners down
                left_corner = face_landmarks.landmark[61].y  # Mouth left
                right_corner = face_landmarks.landmark[291].y  # Mouth right
                nose = face_landmarks.landmark[1].y
                if left_corner > nose and right_corner > nose:
                    expression = 'frown'
                    confidence = 0.7
                # Smile: Mouth up
                elif left_corner < nose - 0.02 and right_corner < nose - 0.02:
                    expression = 'smile'
                    confidence = 0.7
        return expression, confidence

    def infer_move(self):
        frame = self.capture_frame()
        if frame is None:
            return None, 'none', 'neutral', 0.0
        current_grid = self.detect_grid(frame)
        current_fen = grid_to_fen(current_grid)
        gesture, gesture_conf = self.detect_gestures(frame)
        expression, expr_conf = self.detect_expression(frame)
        
        if current_fen == self.previous_fen and gesture == 'none':
            return None, gesture, expression, 0.0
        
        # Confidence for move
        old_grid = fen_to_grid(self.previous_fen)
        diff = current_grid ^ old_grid
        num_changes = np.sum(diff)
        move_conf = 0.0
        move_uci = None
        
        if num_changes == 2:
            move_conf = 0.9
            # Find from/to
            from_candidates = np.where(diff)
            from_row, from_col = from_candidates[0][0], from_candidates[1][0]
            to_row, to_col = from_candidates[0][1], from_candidates[1][1]
            from_square = chess.square(from_col, 7 - from_row)
            to_square = chess.square(to_col, 7 - to_row)
            move_uci = chess.square_name(from_square) + chess.square_name(to_square)
            if not current_grid[from_row, from_col] and current_grid[to_row, to_col]:
                move_conf += 0.1
        overall_conf = move_conf + gesture_conf * 0.2 + expr_conf * 0.1  # Weight gesture/expression
        
        if overall_conf < 0.8:
            print(f"DEBUG: Low confidence ({overall_conf:.2f}) — retrying scan")
            self.previous_fen = current_fen
            return None, gesture, expression, overall_conf
        
        self.previous_fen = current_fen
        print(f"DEBUG: Inferred move {move_uci} with gesture {gesture}, expression {expression}, conf {overall_conf:.2f}")
        return move_uci, gesture, expression, overall_conf

    def close(self):
        self.cap.release()
        self.hands.close()
        self.face.close()