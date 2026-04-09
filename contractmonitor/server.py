"""
FastAPI server — serves the React dashboard and provides API endpoints.
Runs background scanning on a 30-minute interval.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from contractmonitor.config import Config
from contractmonitor.scanner import run_scan
from contractmonitor.notify import send_notification
from contractmonitor.state import StateManager

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent.parent / "frontend" / "dist"

# Global state accessible to the background task
_scan_status = {
    "running": False,
    "last_scan": None,
    "next_scan": None,
    "last_error": None,
    "new_count_last_scan": 0,
}


def create_app(config: Config, state: StateManager) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Start background scanning
        task = asyncio.create_task(_background_scanner(config, state))
        yield
        task.cancel()

    app = FastAPI(title="NYPD Contract Monitor", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/contracts")
    def get_contracts():
        """Return all found contracts."""
        contracts = state.get_all_contracts()
        # Most recent first
        contracts.reverse()
        return {"contracts": contracts, "total": len(contracts)}

    @app.get("/api/scans")
    def get_scans():
        """Return scan history."""
        scans = state.get_scan_history()
        scans.reverse()
        return {"scans": scans[:100]}

    @app.get("/api/status")
    def get_status():
        """Return current scan status."""
        return _scan_status

    @app.post("/api/scan")
    async def trigger_scan():
        """Trigger an immediate scan."""
        if _scan_status["running"]:
            return {"message": "Scan already in progress"}
        asyncio.create_task(_run_single_scan(config, state))
        return {"message": "Scan triggered"}

    # Serve React frontend
    if STATIC_DIR.exists():
        app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

        @app.get("/{full_path:path}")
        async def serve_frontend(full_path: str):
            file_path = STATIC_DIR / full_path
            if file_path.exists() and file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(STATIC_DIR / "index.html")

    return app


async def _run_single_scan(config: Config, state: StateManager):
    """Run a single scan cycle."""
    global _scan_status
    _scan_status["running"] = True
    _scan_status["last_error"] = None
    try:
        new_contracts = await run_scan(config, state)
        _scan_status["new_count_last_scan"] = len(new_contracts)
        _scan_status["last_scan"] = datetime.now().isoformat()
        if new_contracts:
            send_notification(new_contracts, config)
    except Exception as e:
        _scan_status["last_error"] = str(e)
        logger.error(f"Scan failed: {e}")
    finally:
        _scan_status["running"] = False


async def _background_scanner(config: Config, state: StateManager):
    """Background task that scans every N minutes."""
    interval = config.scan_interval_minutes * 60
    while True:
        await _run_single_scan(config, state)
        _scan_status["next_scan"] = datetime.fromtimestamp(
            datetime.now().timestamp() + interval
        ).isoformat()
        logger.info(f"Next scan in {config.scan_interval_minutes} minutes")
        await asyncio.sleep(interval)
