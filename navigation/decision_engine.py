from collections import deque
import logging

logger = logging.getLogger(__name__)

class DecisionEngine:
    """
    Evaluates region obstacle scores and determines the recommended driving direction.
    Incorporates temporal hysteresis to prevent erratic direction switching on noisy frames.
    """
    def __init__(self, obstacle_threshold: float = 0.35, stop_threshold: float = 0.65, hysteresis_frames: int = 3):
        self.obstacle_threshold = obstacle_threshold
        self.stop_threshold = stop_threshold
        self.hysteresis_frames = max(1, hysteresis_frames)

        self.current_decision = "FORWARD"
        self._candidate_history = deque(maxlen=self.hysteresis_frames)

    def evaluate(self, scores: dict) -> str:
        """
        Takes left/center/right obstacle scores (0.0=clear, 1.0=blocked).
        Returns filtered decision recommendation: "FORWARD", "LEFT", "RIGHT", or "STOP".
        """
        left = scores.get("left", 0.0)
        center = scores.get("center", 0.0)
        right = scores.get("right", 0.0)

        # 1. Check for immediate STOP condition (all blocked or center heavily blocked with no side escapes)
        if (center >= self.stop_threshold and left >= self.obstacle_threshold and right >= self.obstacle_threshold) or \
           (left >= self.stop_threshold and center >= self.stop_threshold and right >= self.stop_threshold):
            raw_candidate = "STOP"
        # 2. Check if FORWARD path is clear
        elif center < self.obstacle_threshold:
            raw_candidate = "FORWARD"
        # 3. Center is obstructed: seek side with best clearance
        else:
            if left < right and left < self.stop_threshold:
                raw_candidate = "LEFT"
            elif right <= left and right < self.stop_threshold:
                raw_candidate = "RIGHT"
            else:
                raw_candidate = "STOP"

        # Apply Hysteresis
        self._candidate_history.append(raw_candidate)

        # Only switch decision if all samples in hysteresis window agree on the new candidate
        if len(self._candidate_history) == self.hysteresis_frames:
            if all(c == raw_candidate for c in self._candidate_history):
                if self.current_decision != raw_candidate:
                    logger.info(f"Decision changed: {self.current_decision} -> {raw_candidate}")
                    self.current_decision = raw_candidate

        return self.current_decision
