import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)

class DepthObstacleDetector:
    """
    Monocular Depth Obstacle Detector using MiDaS / PyTorch model.
    Provides identical interface to ClassicalObstacleDetector (`detect`, `annotate_frame`).
    Falls back gracefully if PyTorch/MiDaS is unavailable.
    """
    def __init__(self, model_type: str = "MiDaS_small", roi_top_pct: float = 0.35):
        self.model_type = model_type
        self.roi_top_pct = roi_top_pct
        self._model = None
        self._transform = None
        self._torch = None
        self._device = None
        self._initialized = False

    def _lazy_init(self):
        if self._initialized:
            return True

        try:
            import torch
            self._torch = torch
            self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            logger.info(f"Loading depth model {self.model_type} on device {self._device}...")

            # Load MiDaS small model from PyTorch Hub
            self._model = torch.hub.load("intel-isl/MiDaS", self.model_type)
            self._model.to(self._device)
            self._model.eval()

            midas_transforms = torch.hub.load("intel-isl/MiDaS", "transforms")
            if self.model_type in ["MiDaS_small", "DPT_Hybrid"]:
                self._transform = midas_transforms.small_transform
            else:
                self._transform = midas_transforms.dpt_transform

            self._initialized = True
            logger.info("Depth model loaded successfully!")
            return True
        except Exception as e:
            logger.error(f"Failed to load PyTorch depth model ({e}). Ensure torch & torchvision are installed.")
            return False

    def detect(self, frame: np.ndarray) -> dict:
        if not self._lazy_init():
            # Fallback to zero obstacle density if model failed to load
            return {"left": 0.0, "center": 0.0, "right": 0.0}

        h, w = frame.shape[:2]
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        input_batch = self._transform(img_rgb).to(self._device)

        with self._torch.no_grad():
            prediction = self._model(input_batch)
            prediction = self._torch.nn.functional.interpolate(
                prediction.unsqueeze(1),
                size=(h, w),
                mode="bicubic",
                align_corners=False,
            ).squeeze()

        depth_map = prediction.cpu().numpy()
        # MiDaS outputs relative inverse depth (higher value = closer object = obstacle)

        roi_top = int(h * self.roi_top_pct)
        roi_depth = depth_map[roi_top:h, :]

        # Normalize depth map to 0.0 - 1.0 relative scale within frame
        d_min, d_max = roi_depth.min(), roi_depth.max()
        if d_max > d_min:
            norm_depth = (roi_depth - d_min) / (d_max - d_min)
        else:
            norm_depth = np.zeros_like(roi_depth)

        third_w = w // 3
        left_region = norm_depth[:, 0:third_w]
        center_region = norm_depth[:, third_w:2*third_w]
        right_region = norm_depth[:, 2*third_w:w]

        # Calculate high proximity ratio (percentage of pixels above proximity threshold 0.6)
        scores = {
            "left": float(np.mean(left_region > 0.6)),
            "center": float(np.mean(center_region > 0.6)),
            "right": float(np.mean(right_region > 0.6))
        }

        return scores

    def annotate_frame(self, frame: np.ndarray, scores: dict, decision: str) -> np.ndarray:
        """Reuse visual annotation helper from classical detector style."""
        from .obstacle_detector import ClassicalObstacleDetector
        helper = ClassicalObstacleDetector(roi_top_pct=self.roi_top_pct)
        return helper.annotate_frame(frame, scores, decision)
