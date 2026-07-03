from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
from .telemetry import TelemetryStore
from .rl_optimizer import RLOptimizer

app = FastAPI(title="Spotify AI Mood Discovery API - Phase 4: Telemetry", version="4.0.0")

telemetry_store = TelemetryStore()
rl_optimizer = RLOptimizer()

class TelemetryEvent(BaseModel):
    event_type: str
    session_id: str
    track_id: str
    context_meta: Optional[Dict[str, Any]] = None

@app.post("/api/v1/telemetry/playback-event")
async def log_playback_event(event: TelemetryEvent):
    """
    Ingests playback lifecycle hooks from the player client.
    Example event_type: 'TRACK_SKIPPED', 'TRACK_COMPLETED'
    """
    telemetry_store.log_action(
        event_type=event.event_type,
        session_id=event.session_id,
        track_id=event.track_id,
        context_meta=event.context_meta or {}
    )
    return {"status": "logged", "count": len(telemetry_store.get_logs())}

@app.post("/api/v1/telemetry/run-optimizer")
async def execute_optimization_job():
    """
    Extracts collected logs, runs algorithms to adjust parameter constraints,
    clears processed logs, and returns the newly tuned coefficients.
    """
    logs = telemetry_store.get_logs()
    result = rl_optimizer.run_optimization_cycle(logs)
    
    # Flush logs after analysis
    telemetry_store.clear()
    
    return result

@app.get("/api/v1/telemetry/stats")
async def get_tuning_stats():
    """Returns the globally tuned engine constants."""
    return rl_optimizer.get_current_constants()
