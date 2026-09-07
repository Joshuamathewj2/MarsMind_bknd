import time
import threading
import logging
import cv2
import numpy as np

logger = logging.getLogger(__name__)

class StreamReader:
    """
    Reads an MJPEG video stream (e.g. from IP Webcam app) in a background thread.
    Always maintains and exposes ONLY the single latest decoded frame to prevent queuing backlog.
    Calculates moving-average FPS. Falls back gracefully to synthetic frames if stream is unavailable.
    """
    def __init__(self, stream_url: str, target_width: int = 640, target_height: int = 480):
        self.stream_url = stream_url
        self.target_width = target_width
        self.target_height = target_height

        self._frame = None
        self._fps = 0.0
        self._running = False
        self._thread = None
        self._lock = threading.Lock()

        self._last_frame_time = time.time()
        self._frame_count = 0
        self._fps_timer = time.time()

        # Synthetic generator variables
        self.use_synthetic_fallback = False
        self._synthetic_angle = 0.0

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._thread.start()
        logger.info(f"StreamReader thread started for {self.stream_url}")

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("StreamReader thread stopped")

    def get_frame(self):
        with self._lock:
            if self._frame is None:
                return None, 0.0
            return self._frame.copy(), self._fps

    def _reader_loop(self):
        cap = cv2.VideoCapture(self.stream_url)
        # Reduce buffer size to minimum to ensure immediate latest frame delivery
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        retry_delay = 1.0

        while self._running:
            if not cap.isOpened():
                logger.warning(f"Could not connect to {self.stream_url}. Retrying in {retry_delay}s or using synthetic stream...")
                self.use_synthetic_fallback = True
                time.sleep(retry_delay)
                cap.release()
                cap = cv2.VideoCapture(self.stream_url)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                
                # If stream opens successfully after retry, switch off synthetic mode
                if cap.isOpened() and cap.grab():
                    self.use_synthetic_fallback = False

            if self.use_synthetic_fallback:
                frame = self._generate_synthetic_frame()
                self._update_frame(frame)
                time.sleep(1.0 / 30.0)  # ~30 FPS synthetic
                continue

            ret, raw_frame = cap.read()
            if not ret or raw_frame is None:
                logger.warning("Failed to grab frame from stream. Falling back to synthetic frames temporarily.")
                self.use_synthetic_fallback = True
                time.sleep(0.5)
                continue

            # Frame grabbed successfully
            if (raw_frame.shape[1] != self.target_width) or (raw_frame.shape[0] != self.target_height):
                frame = cv2.resize(raw_frame, (self.target_width, self.target_height))
            else:
                frame = raw_frame

            self._update_frame(frame)

        cap.release()

    def _update_frame(self, frame):
        now = time.time()
        self._frame_count += 1
        elapsed = now - self._fps_timer
        if elapsed >= 1.0:
            self._fps = self._frame_count / elapsed
            self._frame_count = 0
            self._fps_timer = now

        with self._lock:
            self._frame = frame

    def _generate_synthetic_frame(self) -> np.ndarray:
        """Generates an animated test obstacle frame for simulation/testing when live feed is absent."""
        frame = np.zeros((self.target_height, self.target_width, 3), dtype=np.uint8)
        
        # Grid lines background
        for y in range(0, self.target_height, 40):
            cv2.line(frame, (0, y), (self.target_width, y), (30, 30, 30), 1)
        for x in range(0, self.target_width, 40):
            cv2.line(frame, (x, 0), (x, self.target_height), (30, 30, 30), 1)

        # Draw a synthetic moving obstacle (box)
        self._synthetic_angle += 0.05
        box_x = int((self.target_width / 2) + np.sin(self._synthetic_angle) * (self.target_width * 0.35))
        box_y = int(self.target_height * 0.65)
        
        cv2.rectangle(frame, (box_x - 40, box_y - 40), (box_x + 40, box_y + 40), (0, 0, 220), -1)
        cv2.putText(frame, "SIMULATED STREAM (NO CAMERA DETECTED)", (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.putText(frame, f"URL: {self.stream_url}", (20, 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

        return frame
