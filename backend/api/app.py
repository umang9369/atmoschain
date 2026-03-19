"""
ATMOSCHAIN — FastAPI Backend
app.py

Main FastAPI application entry point.
Configures CORS, mounts all route modules, and provides WebSocket hub
for live webcam streaming.

Run with:
  cd d:/Projects/ATMOSCHAIN
  uvicorn backend.api.app:app --reload --port 8000

Author: ATMOSCHAIN Dev Team
"""

import sys
import os

# Add project root to path so all imports resolve correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import logging
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.wastevision_routes  import router as wastevision_router
from backend.api.plasmasim_routes    import router as plasmasim_router
from backend.api.carbonchain_routes  import router as carbonchain_router

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("ATMOSCHAIN")

# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title       = "ATMOSCHAIN API",
    description = "AI-powered waste management intelligence platform",
    version     = "1.0.0",
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
# Allow Next.js dev server (localhost:3000) and any preview URLs
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(wastevision_router)
app.include_router(plasmasim_router)
app.include_router(carbonchain_router)

# ─── Health check ─────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    # Forced reload 2
    return {
        "status"  : "operational",
        "modules" : ["WasteVision", "PlasmaSim", "CCTS SmartMarket"],
        "version" : "1.0.0",
        "message" : "ATMOSCHAIN API is live"
    }

@app.get("/")
async def root():
    return {
        "app"    : "ATMOSCHAIN",
        "docs"   : "http://localhost:8000/docs",
        "health" : "http://localhost:8000/health",
        "routes" : {
            "detect"      : "POST /api/detect",
            "heatmap"     : "GET  /api/heatmap",
            "simulate"    : "POST /api/simulate",
            "mint"        : "POST /api/mint",
            "market"      : "GET  /api/market",
            "buy"         : "POST /api/buy",
            "impact"      : "GET  /api/impact",
        }
    }

# ─── WebSocket: Live video frame analysis ─────────────────────────────────────
class ConnectionManager:
    """Manages active WebSocket connections for live analysis."""

    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        logger.info(f"WebSocket connected. Active: {len(self.active)}")

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)
        logger.info(f"WebSocket disconnected. Active: {len(self.active)}")

    async def broadcast(self, message: dict):
        for ws in list(self.active):
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(ws)


manager = ConnectionManager()


@app.websocket("/ws/live")
async def live_analysis(websocket: WebSocket):
    """
    WebSocket endpoint for live webcam frame analysis.
    Client sends base64 JPEG frames → server responds with detection results.
    
    Message format (client → server):
        { "frame": "<base64 JPEG>", "mass_override_kg": <optional float> }
    
    Response format (server → client):
        Full detection + methane + combined result dict
    """
    await manager.connect(websocket)
    try:
        # Lazy import detector inside WS to avoid startup delay
        from ml_models.wastevision.waste_detector import WasteDetector
        from backend.services.methane_engine import calculate_methane_impact

        detector = WasteDetector()

        while True:
            data = await websocket.receive_json()
            frame_b64   = data.get("frame", "")
            mass_override = data.get("mass_override_kg")

            if not frame_b64:
                await websocket.send_json({"error": "No frame provided"})
                continue

            try:
                detection = detector.detect_from_base64(frame_b64)
                mass_kg   = mass_override or detection.get("estimated_mass_kg", 0.1)
                methane   = calculate_methane_impact(detection.get("waste_class", "unknown"), mass_kg)

                await websocket.send_json({
                    "type"     : "detection_result",
                    "detection": detection,
                    "methane"  : methane,
                    "combined" : {
                        "waste_class"    : detection.get("waste_class"),
                        "confidence"     : detection.get("confidence"),
                        "item"           : detection.get("item_description"),
                        "mass_kg"        : mass_kg,
                        "ch4_kg"         : methane.get("ch4_kg"),
                        "co2e_kg"        : methane.get("co2e_kg"),
                        "carbon_credits" : methane.get("carbon_credits"),
                        "revenue_inr_mid": methane.get("revenue_inr_mid"),
                        "biodegradable"  : detection.get("biodegradable"),
                        "recyclable"     : detection.get("recyclable"),
                        "hazardous"      : detection.get("hazardous"),
                    }
                })
            except Exception as e:
                await websocket.send_json({"error": str(e)})

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# ─── Exception handler ────────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.api.app:app", host="0.0.0.0", port=8000, reload=True)
