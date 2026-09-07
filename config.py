import os

"""
===================================================================================
RC CAR CO-PILOT SYSTEM CONFIGURATION
===================================================================================
NOTE ON SYSTEM BOUNDARIES & COMMUNICATION:
This system ONLY consumes an incoming MJPEG video stream from a smartphone camera.
There is NO connection, API, telemetry link, or control interface between this
backend/laptop and the RC car or its transmitter. All vehicle steering is performed 
manually by a human driver operating the stock RC transmitter.
===================================================================================
"""

# Phone IP Webcam MJPEG Stream settings
STREAM_URL = os.getenv("RC_STREAM_URL", "http://192.168.1.100:8080/video")
FRAME_WIDTH = int(os.getenv("RC_FRAME_WIDTH", "640"))
FRAME_HEIGHT = int(os.getenv("RC_FRAME_HEIGHT", "480"))

# Vision & Detector settings ('classical' or 'depth')
DETECTOR_TYPE = os.getenv("RC_DETECTOR", "classical")

# Obstacle score thresholds (range 0.0 - 1.0)
# Score represents how blocked a region is. Higher = more blocked.
OBSTACLE_THRESHOLD = float(os.getenv("RC_OBSTACLE_THRESHOLD", "0.35"))
STOP_THRESHOLD = float(os.getenv("RC_STOP_THRESHOLD", "0.65"))

# Navigation & Decision settings
HYSTERESIS_FRAMES = int(os.getenv("RC_HYSTERESIS_FRAMES", "3"))
ASSUMED_SPEED = float(os.getenv("RC_ASSUMED_SPEED", "0.3"))  # meters per step/tick
TURN_ANGLE = float(os.getenv("RC_TURN_ANGLE", "30.0"))        # degrees for turning ticks

# Server settings
SERVER_HOST = os.getenv("RC_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("RC_PORT", "8000"))
