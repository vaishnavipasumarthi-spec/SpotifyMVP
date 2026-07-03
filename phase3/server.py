import os
import time
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response

# Import Phase 2 server
try:
    from phase2.main import app as phase2_app
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from phase2.main import app as phase2_app

app = FastAPI(title="Spotify AI Mood Discovery - Phase 3", version="3.0.0")

# Include Phase 2 API routes
app.include_router(phase2_app.router)

# Serve static assets with NO-CACHE headers to prevent browser caching stale JS/HTML
current_dir = os.path.dirname(os.path.abspath(__file__))

@app.get("/")
async def serve_index():
    resp = FileResponse(os.path.join(current_dir, "index.html"), media_type="text/html")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

@app.get("/index.js")
async def serve_js():
    resp = FileResponse(os.path.join(current_dir, "index.js"), media_type="application/javascript")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp

@app.get("/index.css")
async def serve_css():
    resp = FileResponse(os.path.join(current_dir, "index.css"), media_type="text/css")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp
