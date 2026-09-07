import asyncio
import base64
import time
import logging
from typing import Set
import cv2

# Compatibility patch for Starlette 1.3+ / FastAPI router init kwarg mismatch
import starlette.routing
_orig_router_init = starlette.routing.Router.__init__
def _patched_router_init(self, *args, **kwargs):
    kwargs.pop("on_startup", None)
    kwargs.pop("on_shutdown", None)
    return _orig_router_init(self, *args, **kwargs)
starlette.routing.Router.__init__ = _patched_router_init

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse


import config
from ingestion import StreamReader
from vision import ClassicalObstacleDetector
from navigation import DecisionEngine, PathTracker

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("server")

from contextlib import asynccontextmanager

# Global Active WebSocket Connections Set
active_websockets: Set[WebSocket] = set()

# Initialize Components
stream_reader = StreamReader(
    stream_url=config.STREAM_URL,
    target_width=config.FRAME_WIDTH,
    target_height=config.FRAME_HEIGHT
)

# Instantiate vision detector according to config
if config.DETECTOR_TYPE == "depth":
    logger.info("Initializing DepthObstacleDetector...")
    try:
        from vision.depth_detector import DepthObstacleDetector
        detector = DepthObstacleDetector()
    except Exception as err:
        logger.warning(f"Depth detector init failed ({err}). Falling back to ClassicalObstacleDetector.")
        detector = ClassicalObstacleDetector()
else:
    logger.info("Initializing ClassicalObstacleDetector...")
    detector = ClassicalObstacleDetector()

decision_engine = DecisionEngine(
    obstacle_threshold=config.OBSTACLE_THRESHOLD,
    stop_threshold=config.STOP_THRESHOLD,
    hysteresis_frames=config.HYSTERESIS_FRAMES
)

path_tracker = PathTracker(
    step_distance=config.ASSUMED_SPEED,
    turn_angle_deg=config.TURN_ANGLE
)

# Background Perception Task Reference
perception_task = None

async def perception_loop():
    """
    Continuous background loop running perception + decision + dead reckoning.
    Encodes latest frame to JPEG base64 and broadcasts non-blockingly to WebSocket clients.
    """
    logger.info("Perception loop started")
    while True:
        try:
            frame, fps = stream_reader.get_frame()
            if frame is None:
                await asyncio.sleep(0.05)
                continue

            # Offload blocking computer vision processing to thread pool
            scores = await asyncio.to_thread(detector.detect, frame)
            
            # Compute driving recommendation
            decision = decision_engine.evaluate(scores)

            # Update dead-reckoning trajectory estimate
            path_point = path_tracker.update(decision)

            # Annotate HUD frame for streaming
            annotated_frame = await asyncio.to_thread(detector.annotate_frame, frame, scores, decision)

            # Encode frame to JPEG buffer
            _, buffer = await asyncio.to_thread(cv2.imencode, ".jpg", annotated_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
            frame_b64 = base64.b64encode(buffer).decode("utf-8")

            # Prepare broadcast payload
            payload = {
                "frame_b64": frame_b64,
                "decision": decision,
                "region_scores": scores,
                "path_point": path_point,
                "fps": round(fps, 1),
                "timestamp": round(time.time(), 3),
                "detector": config.DETECTOR_TYPE
            }

            # Non-blocking broadcast to all active WebSocket connections
            if active_websockets:
                closed_sockets = set()
                for ws in list(active_websockets):
                    try:
                        await ws.send_json(payload)
                    except Exception:
                        closed_sockets.add(ws)
                
                # Clean up disconnected sockets
                for ws in closed_sockets:
                    active_websockets.discard(ws)

            # Yield control to prevent event-loop starvation (~30 Hz max rate)
            await asyncio.sleep(0.03)

        except asyncio.CancelledError:
            logger.info("Perception loop cancelled")
            break
        except Exception as e:
            logger.error(f"Error in perception loop: {e}", exc_info=True)
            await asyncio.sleep(0.1)

app = FastAPI(title="RC Car Obstacle-Avoidance Co-Pilot")

# Startup background tasks safely across FastAPI/Starlette versions
def start_perception():
    global perception_task
    stream_reader.start()
    try:
        loop = asyncio.get_running_loop()
        perception_task = loop.create_task(perception_loop())
    except RuntimeError:
        pass

@app.get("/health")
async def health_check():
    global perception_task
    if perception_task is None or perception_task.done():
        try:
            loop = asyncio.get_running_loop()
            perception_task = loop.create_task(perception_loop())
        except RuntimeError:
            pass
    _, fps = stream_reader.get_frame()
    return JSONResponse({
        "status": "ok",
        "fps": round(fps, 1),
        "detector": config.DETECTOR_TYPE,
        "active_clients": len(active_websockets),
        "synthetic_fallback": stream_reader.use_synthetic_fallback
    })


@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    await websocket.accept()
    active_websockets.add(websocket)
    logger.info(f"New dashboard client connected. Total clients: {len(active_websockets)}")
    try:
        while True:
            # Keep connection open & handle incoming client control messages (e.g. path reset)
            data = await websocket.receive_text()
            if data == "reset_path":
                path_tracker.reset()
                logger.info("Path tracker reset requested by dashboard client")
    except WebSocketDisconnect:
        logger.info("Dashboard client disconnected")
    except Exception as e:
        logger.warning(f"WebSocket client error: {e}")
    finally:
        active_websockets.discard(websocket)

# Serve static dashboard files
app.mount("/static", StaticFiles(directory="server/static/dashboard"), name="static")

@app.get("/")
async def read_index():
    return FileResponse("server/static/dashboard/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.main:app", host=config.SERVER_HOST, port=config.SERVER_PORT, reload=False)
