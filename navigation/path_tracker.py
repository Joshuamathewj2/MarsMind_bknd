import math
import logging

logger = logging.getLogger(__name__)

class PathTracker:
    """
    ===================================================================================
    NOTE & DISCLAIMER:
    This path tracker provides a rough DEAD-RECKONING trajectory estimate based purely
    on the *recommended* co-pilot directions over time. Since there is no onboard 
    microcontroller, IMU, or wheel encoder telemetry feedback from the RC car, this 
    path represents an estimated open-loop spatial trace, assuming the human driver 
    follows the co-pilot recommendations at nominal vehicle speed.
    ===================================================================================
    """
    def __init__(self, step_distance: float = 0.3, turn_angle_deg: float = 30.0):
        """
        :param step_distance: Assumed displacement distance per forward move step (in meters)
        :param turn_angle_deg: Assumed heading turn angle change per step (in degrees)
        """
        self.step_distance = step_distance
        self.turn_angle_deg = turn_angle_deg

        # Pose state: (x, y) in meters, heading in degrees (0 = Facing North / +Y axis)
        self.x = 0.0
        self.y = 0.0
        self.heading_deg = 0.0

        # History of path coordinates [(x, y), ...]
        self.path_history = [(0.0, 0.0)]
        self.max_history = 200

    def update(self, recommendation: str) -> dict:
        """
        Updates the estimated vehicle pose based on the latest recommended decision.
        Returns dict containing current position, heading, and recent path history points.
        """
        if recommendation == "FORWARD":
            # Move forward along current heading
            rad = math.radians(self.heading_deg)
            self.x += self.step_distance * math.sin(rad)
            self.y += self.step_distance * math.cos(rad)
            self.path_history.append((round(self.x, 2), round(self.y, 2)))

        elif recommendation == "LEFT":
            # Rotate heading counter-clockwise (left) and advance
            self.heading_deg = (self.heading_deg - self.turn_angle_deg) % 360.0
            rad = math.radians(self.heading_deg)
            self.x += self.step_distance * 0.5 * math.sin(rad)
            self.y += self.step_distance * 0.5 * math.cos(rad)
            self.path_history.append((round(self.x, 2), round(self.y, 2)))

        elif recommendation == "RIGHT":
            # Rotate heading clockwise (right) and advance
            self.heading_deg = (self.heading_deg + self.turn_angle_deg) % 360.0
            rad = math.radians(self.heading_deg)
            self.x += self.step_distance * 0.5 * math.sin(rad)
            self.y += self.step_distance * 0.5 * math.cos(rad)
            self.path_history.append((round(self.x, 2), round(self.y, 2)))

        elif recommendation == "STOP":
            # Stationary - no coordinate update
            pass

        # Trim history if exceeding max size
        if len(self.path_history) > self.max_history:
            self.path_history.pop(0)

        return {
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "heading": round(self.heading_deg, 1),
            "path": self.path_history
        }

    def reset(self):
        """Resets dead reckoning state to origin (0, 0)."""
        self.x = 0.0
        self.y = 0.0
        self.heading_deg = 0.0
        self.path_history = [(0.0, 0.0)]
