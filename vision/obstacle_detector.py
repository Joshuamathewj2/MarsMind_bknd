import cv2
import numpy as np

class ClassicalObstacleDetector:
    """
    Classical CV Obstacle Detector.
    Uses edge density and texture gradients across left/center/right vertical thirds of the lower ground ROI.
    Requires no external neural network models — fast, offline, and deterministic.
    """
    def __init__(self, roi_top_pct: float = 0.35):
        """
        :param roi_top_pct: Percentage from the top to start looking (0.35 = look at bottom 65% of frame)
        """
        self.roi_top_pct = roi_top_pct

    def detect(self, frame: np.ndarray) -> dict:
        """
        Takes a frame and computes clearance / obstacle scores for left, center, right regions.
        Returns:
            scores dict: {"left": float, "center": float, "right": float} (0.0 = clear, 1.0 = blocked)
        """
        h, w = frame.shape[:2]
        roi_top = int(h * self.roi_top_pct)
        roi = frame[roi_top:h, :]

        # Grayscale & Gaussian Blur
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Canny edge detection
        edges = cv2.Canny(blurred, 50, 150)

        # Sobel gradient magnitude for textured obstacles
        sobelx = cv2.Sobel(blurred, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=3)
        grad_mag = np.sqrt(sobelx**2 + sobely**2)
        grad_mag = cv2.normalize(grad_mag, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

        # Combine edges and gradient magnitude
        combined = cv2.addWeighted(edges, 0.6, grad_mag, 0.4, 0)

        third_w = w // 3

        # Sub-divide into left, center, right regions
        left_region = combined[:, 0:third_w]
        center_region = combined[:, third_w:2*third_w]
        right_region = combined[:, 2*third_w:w]

        # Calculate density (mean edge pixel intensity ratio)
        left_raw = np.mean(left_region) / 255.0
        center_raw = np.mean(center_region) / 255.0
        right_raw = np.mean(right_region) / 255.0

        # Scale raw densities to [0.0, 1.0] range using a calibrated sensitivity curve
        # Typical clear floor edge density is ~0.05-0.10, dense obstacle is >0.25
        scores = {
            "left": float(np.clip((left_raw - 0.05) / 0.25, 0.0, 1.0)),
            "center": float(np.clip((center_raw - 0.05) / 0.25, 0.0, 1.0)),
            "right": float(np.clip((right_raw - 0.05) / 0.25, 0.0, 1.0))
        }

        return scores

    def annotate_frame(self, frame: np.ndarray, scores: dict, decision: str) -> np.ndarray:
        """
        Draws visual HUD overlay on the frame for dashboard streaming.
        """
        annotated = frame.copy()
        h, w = annotated.shape[:2]
        roi_top = int(h * self.roi_top_pct)
        third_w = w // 3

        # Color maps based on obstacle severity
        def get_color(score):
            if score > 0.65:
                return (0, 0, 255)      # Red - Danger
            elif score > 0.35:
                return (0, 165, 255)    # Amber - Caution
            return (0, 255, 0)          # Green - Clear

        # Draw ROI divider line
        cv2.line(annotated, (0, roi_top), (w, roi_top), (255, 255, 255), 1, cv2.LINE_AA)

        # Draw Vertical Third Dividers
        cv2.line(annotated, (third_w, roi_top), (third_w, h), (255, 255, 255), 2, cv2.LINE_AA)
        cv2.line(annotated, (2 * third_w, roi_top), (2 * third_w, h), (255, 255, 255), 2, cv2.LINE_AA)

        # Semi-transparent region highlights
        overlay = annotated.copy()
        regions = [
            ("LEFT", 0, third_w, scores["left"]),
            ("CENTER", third_w, 2 * third_w, scores["center"]),
            ("RIGHT", 2 * third_w, w, scores["right"])
        ]

        for name, start_x, end_x, score in regions:
            color = get_color(score)
            cv2.rectangle(overlay, (start_x, roi_top), (end_x, h), color, -1)

            # Score text
            label = f"{name}: {int(score * 100)}%"
            cv2.putText(annotated, label, (start_x + 15, roi_top + 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)

        # Blend overlay (alpha transparency = 0.25)
        cv2.addWeighted(overlay, 0.25, annotated, 0.75, 0, annotated)

        # Overlay decision banner at top
        banner_color = (0, 255, 0) if decision == "FORWARD" else (0, 0, 255) if decision == "STOP" else (0, 165, 255)
        cv2.rectangle(annotated, (0, 0), (w, 45), (20, 20, 20), -1)
        cv2.putText(annotated, f"CO-PILOT RECOMMENDATION: {decision}", (15, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, banner_color, 2, cv2.LINE_AA)

        return annotated
