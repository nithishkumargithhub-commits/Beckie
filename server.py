import os
import sys
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psutil

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config
import actions.database as database
from intent.classifier import IntentClassifier
from actions.reminders import create_calendar_reminder, list_calendar_reminders
from actions.google_services import (
    add_google_task, list_google_tasks, complete_google_task,
    check_unread_emails, send_email
)
from actions.reminder_daemon import reminder_daemon
from main import _process_command_inner

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("VoiceAssistant.Server")

app = FastAPI(title="Jarvis Assistant REST API & Web Dashboard", version="2.0.0")

# Enable CORS for mobile apps and cross-origin clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

classifier = IntentClassifier()

# WebSocket Manager for real-time notifications
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to WebSocket: {e}")

ws_manager = ConnectionManager()

main_loop = None

@app.on_event("startup")
async def startup_event():
    global main_loop
    main_loop = asyncio.get_running_loop()
    try:
        from backend.telemetry import get_telemetry_service
        await get_telemetry_service().start()
    except Exception as e:
        logger.warning(f"Could not start telemetry service: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    try:
        from backend.telemetry import get_telemetry_service
        await get_telemetry_service().stop()
    except Exception as e:
        logger.warning(f"Error stopping telemetry service: {e}")


# Event Loop Threadsafe Broadcast Helper for ReminderDaemon
def broadcast_daemon_notification(payload: dict):
    """Callback function registered with reminder_daemon to broadcast WebSocket alerts."""
    try:
        if main_loop and main_loop.is_running():
            asyncio.run_coroutine_threadsafe(ws_manager.broadcast(payload), main_loop)
    except Exception as e:
        logger.warning(f"Could not dispatch async broadcast: {e}")

# Register WebSocket broadcast callback with reminder daemon and avatar event publisher
reminder_daemon.register_callback(broadcast_daemon_notification)
reminder_daemon.start()

try:
    from backend.avatar.avatar_event_publisher import get_avatar_event_publisher
    get_avatar_event_publisher().register_listener(broadcast_daemon_notification)
except Exception as e:
    logger.warning(f"Could not register avatar event listener: {e}")


from fastapi import Header, Query, Depends

async def verify_api_key(
    x_api_key: str = Header(None, alias="X-API-Key"),
    api_key: str = Query(None)
):
    """
    Validates requests against config.JARVIS_API_KEY if configured.
    """
    expected_key = getattr(config, "JARVIS_API_KEY", "")
    if expected_key:
        provided = x_api_key or api_key
        if not provided or provided != expected_key:
            raise HTTPException(status_code=401, detail="Unauthorized: Invalid or missing API Key.")

class CommandRequest(BaseModel):
    command: str

@app.post("/api/command", dependencies=[Depends(verify_api_key)])
async def handle_command_api(req: CommandRequest):
    """
    Executes a voice or text command and returns the structured result.
    """
    user_text = req.command.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="Command string cannot be empty.")

    logger.info(f"REST API received command: '{user_text}'")

    spoken_messages = []
    def fake_speak(msg: str):
        spoken_messages.append(msg)
        logger.info(f"Assistant Spoke: {msg}")

    try:
        success, executed_intent = _process_command_inner(user_text, stream=None, speak=fake_speak)
        response_text = "\n".join(spoken_messages) if spoken_messages else "Action completed."
        
        # Log to SQLite DB
        database.save_interaction(user_text, response_text, str(executed_intent))

        return {
            "success": success,
            "intent": str(executed_intent),
            "response": response_text
        }
    except Exception as e:
        logger.error(f"Error executing command via API: {e}")
        return {
            "success": False,
            "intent": "error",
            "response": f"Failed to execute command: {e}"
        }


@app.get("/api/reminders", dependencies=[Depends(verify_api_key)])
async def get_reminders_api():
    """Returns upcoming reminders and calendar events."""
    success, msg = list_calendar_reminders(max_results=10)
    local_rems = database.get_local_reminders(limit=10)
    return {
        "success": success,
        "summary": msg,
        "reminders": local_rems
    }


# ------------------ Calendar, Tasks & Spotify APIs ------------------

class TaskCreateRequest(BaseModel):
    title: str
    notes: Optional[str] = None

class TaskToggleRequest(BaseModel):
    task_id: str
    completed: bool

class CalendarCreateRequest(BaseModel):
    title: str
    datetime_str: Optional[str] = None

class SpotifyControlRequest(BaseModel):
    action: str  # "play", "pause", "skip_next", "skip_previous", "toggle"
    query: Optional[str] = None

class SpotifyExchangeRequest(BaseModel):
    code_or_url: str
    redirect_uri: Optional[str] = None


@app.get("/api/calendar/events")
async def get_calendar_events_api():
    """Returns live upcoming Google Calendar events."""
    from actions.google_services import get_structured_calendar_events
    events = get_structured_calendar_events()
    return {"success": True, "events": events}


@app.get("/api/calendar/week")
async def get_calendar_week_api():
    """Returns structured 7-day week agenda for 3D Main Dashboard."""
    from actions.google_services import get_week_agenda
    week = get_week_agenda(days=7)
    total_events = sum(len(d.get("events", [])) for d in week)
    return {"success": True, "week_agenda": week, "total_events": total_events}


@app.post("/api/calendar/events")
async def create_calendar_event_api(req: CalendarCreateRequest):
    """Schedules a new Google Calendar event."""
    from actions.google_services import add_calendar_event
    success, msg = add_calendar_event(req.title, req.datetime_str)
    return {"success": success, "message": msg}


@app.get("/api/tasks")
async def get_tasks_api():
    """Returns active and recent Google Tasks."""
    from actions.google_services import get_structured_tasks
    tasks = get_structured_tasks()
    return {"success": True, "tasks": tasks}


@app.post("/api/tasks")
async def create_task_api(req: TaskCreateRequest):
    """Creates a new Google Task."""
    from actions.google_services import add_google_task
    success, msg = add_google_task(req.title, req.notes)
    return {"success": success, "message": msg}


@app.post("/api/tasks/toggle")
async def toggle_task_api(req: TaskToggleRequest):
    """Toggles Google Task completed status."""
    from actions.google_services import set_task_completed
    success, msg = set_task_completed(req.task_id, req.completed)
    return {"success": success, "message": msg}


@app.get("/api/spotify/current")
async def get_spotify_current_api():
    """Returns currently playing Spotify track."""
    from actions.spotify_integration import get_current_track_data
    data = get_current_track_data()
    return {"success": True, "track": data}


@app.get("/api/spotify/auth-url")
async def get_spotify_auth_url_api(redirect_uri: Optional[str] = None):
    """Generates the Spotify authorization URL."""
    import actions.spotify_integration as sp
    uri = redirect_uri or "http://127.0.0.1:8888/callback"
    try:
        url = sp.get_auth_url(uri)
        return {
            "success": True,
            "auth_url": url,
            "redirect_uri": uri,
            "is_authenticated": sp.is_spotify_authenticated()
        }
    except Exception as e:
        return {"success": False, "error": str(e), "is_authenticated": sp.is_spotify_authenticated()}


@app.post("/api/spotify/exchange")
async def exchange_spotify_code_api(req: SpotifyExchangeRequest):
    """Exchanges an authorization code or redirect URL for Spotify tokens."""
    import actions.spotify_integration as sp
    success, msg = sp.exchange_code_for_token(req.code_or_url, req.redirect_uri)
    return {"success": success, "message": msg}


@app.get("/api/spotify/callback")
async def spotify_callback_api(code: Optional[str] = None, error: Optional[str] = None):
    """Direct callback handler if Spotify redirects to FastAPI server."""
    if error:
        return HTMLResponse(f"<h3>Spotify Auth Failed</h3><p>{error}</p>", status_code=400)
    if not code:
        return HTMLResponse("<h3>No code provided</h3>", status_code=400)
    import actions.spotify_integration as sp
    success, msg = sp.exchange_code_for_token(code, "http://127.0.0.1:8000/api/spotify/callback")
    if success:
        return HTMLResponse("<html><body style='background:#030716;color:#00B8FF;font-family:sans-serif;text-align:center;padding-top:60px;'><h2>BECKIE // SPOTIFY CONNECTED</h2><p>You can close this tab now.</p></body></html>")
    return HTMLResponse(f"<h3>Auth Exchange Error</h3><p>{msg}</p>", status_code=500)


class SpotifyPlayRequest(BaseModel):
    query: Optional[str] = None

class PlaylistCreateRequest(BaseModel):
    name: str
    uri_or_url: str
    tag: Optional[str] = "CUSTOM"

class PreferencesUpdateRequest(BaseModel):
    preferences: Dict[str, Any]


@app.get("/api/spotify/playlists")
async def get_spotify_playlists_api():
    """Returns user playlists and pinned playlists."""
    import actions.spotify_integration as sp
    pls = sp.get_playlists()
    return {"success": True, "playlists": pls}


@app.post("/api/spotify/playlists")
async def add_spotify_playlist_api(req: PlaylistCreateRequest):
    """Pins a custom playlist to user dashboard."""
    import actions.spotify_integration as sp
    success, msg = sp.add_custom_playlist(req.name, req.uri_or_url, req.tag or "CUSTOM")
    return {"success": success, "message": msg}


@app.get("/api/spotify/preferences")
async def get_spotify_preferences_api():
    """Returns user music and visualizer preferences."""
    import actions.spotify_integration as sp
    prefs = sp.get_preferences()
    return {"success": True, "preferences": prefs}


@app.post("/api/spotify/preferences")
async def update_spotify_preferences_api(req: PreferencesUpdateRequest):
    """Updates user music preferences."""
    import actions.spotify_integration as sp
    updated = sp.update_preferences(req.preferences)
    return {"success": True, "preferences": updated}


@app.post("/api/spotify/play")
async def play_spotify_api(req: SpotifyPlayRequest):
    """Searches and starts playback of a track or playlist on Spotify."""
    import actions.spotify_integration as sp
    success, msg = sp.play(req.query)
    return {"success": success, "message": msg}



@app.post("/api/spotify/launch")
async def launch_spotify_api():
    """Launches Spotify desktop application or opens web player."""
    import actions.spotify_integration as sp
    success, msg = sp.launch_app()
    return {"success": success, "message": msg}


@app.post("/api/spotify/control")
async def control_spotify_api(req: SpotifyControlRequest):
    """Controls Spotify playback (play/pause/skip/launch)."""
    import actions.spotify_integration as sp
    action = req.action.lower()
    if action == "play":
        success, msg = sp.play(req.query)
    elif action == "pause":
        success, msg = sp.pause()
    elif action in ("next", "skip_next"):
        success, msg = sp.skip_next()
    elif action in ("previous", "prev", "skip_previous"):
        success, msg = sp.skip_previous()
    elif action in ("launch", "open_app"):
        success, msg = sp.launch_app()
    elif action == "toggle":
        curr = sp.get_current_track_data()
        if curr.get("is_playing"):
            success, msg = sp.pause()
        else:
            success, msg = sp.play(req.query)
    else:
        return {"success": False, "message": f"Unknown action: {action}"}
    return {"success": success, "message": msg}





@app.get("/api/status", dependencies=[Depends(verify_api_key)])
async def get_system_status_api():
    """Returns server and host machine metrics."""
    cpu_percent = psutil.cpu_percent(interval=0.1)
    ram_percent = psutil.virtual_memory().percent
    calendar_connected = os.path.exists(os.path.join(config.BASE_DIR, "credentials.json"))

    return {
        "status": "online",
        "cpu": cpu_percent,
        "ram": ram_percent,
        "google_calendar_connected": calendar_connected,
        "active_websocket_clients": len(ws_manager.active_connections)
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, api_key: str = Query(None)):
    """Real-time WebSocket connection for live notification alerts."""
    expected_key = getattr(config, "JARVIS_API_KEY", "")
    if expected_key and api_key != expected_key:
        await websocket.close(code=1008)
        return

    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo ping/pong or process live commands
            await websocket.send_json({"event": "ack", "received": data})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# ------------------ Emotion & Adaptive Dialogue APIs ------------------
class EmotionSettingsUpdate(BaseModel):
    emotion_enabled: Optional[bool] = None
    neutral_mode: Optional[bool] = None
    show_emotion_state: Optional[bool] = None

class EmotionInferRequest(BaseModel):
    text: str
    session_id: Optional[str] = None

@app.get("/api/emotion/state")
def get_emotion_state_endpoint():
    from security.privacy_controls import get_privacy_manager
    from core.emotion_engine import get_emotion_engine
    from core.dialogue_manager import get_dialogue_manager

    pm = get_privacy_manager()
    engine = get_emotion_engine()
    dm = get_dialogue_manager()

    adaptation = dm.get_current_adaptation()
    return {
        "status": "success",
        "settings": pm.settings.to_dict(),
        "current_emotion": engine.get_current_state().to_dict(),
        "current_adaptation": adaptation.to_dict() if adaptation else None,
    }

@app.post("/api/emotion/settings")
def update_emotion_settings_endpoint(payload: EmotionSettingsUpdate):
    from security.privacy_controls import get_privacy_manager
    pm = get_privacy_manager()
    updated = pm.update_settings(
        emotion_enabled=payload.emotion_enabled,
        neutral_mode=payload.neutral_mode,
        show_emotion_state=payload.show_emotion_state,
    )
    return {"status": "success", "settings": updated.to_dict()}

@app.post("/api/emotion/clear")
def clear_emotion_endpoint():
    from security.privacy_controls import get_privacy_manager
    pm = get_privacy_manager()
    deleted = pm.clear_emotion_history()
    return {"status": "success", "deleted_count": deleted}

@app.post("/api/emotion/infer")
def infer_emotion_endpoint(payload: EmotionInferRequest):
    from security.privacy_controls import get_privacy_manager
    from core.emotion_engine import get_emotion_engine
    from core.dialogue_manager import get_dialogue_manager

    pm = get_privacy_manager()
    engine = get_emotion_engine()
    dm = get_dialogue_manager()

    state = engine.process_turn(payload.text)
    adaptation = dm.adapt(state)

    sid = payload.session_id or "web_session"
    pm.save_turn_record(sid, turn_index=len(engine._history), emotion=state, adaptation=adaptation)

    return {
        "status": "success",
        "emotion_state": state.to_dict(),
        "adaptation": adaptation.to_dict(),
    }


# ---------------------------------------------------------------------------
# Hardware Telemetry Endpoints (Local Read-Only NVML / LHM / OEM Adapters)
# ---------------------------------------------------------------------------

class TelemetryPauseRequest(BaseModel):
    paused: bool

@app.get("/api/telemetry/gpu")
def get_gpu_telemetry_endpoint():
    from backend.telemetry import get_telemetry_service
    svc = get_telemetry_service()
    return svc.get_latest_snapshot().gpu.model_dump()

@app.get("/api/telemetry/cpu")
def get_cpu_telemetry_endpoint():
    from backend.telemetry import get_telemetry_service
    svc = get_telemetry_service()
    return svc.get_latest_snapshot().cpu.model_dump()

@app.get("/api/telemetry/all")
def get_all_telemetry_endpoint():
    from backend.telemetry import get_telemetry_service
    svc = get_telemetry_service()
    snapshot = svc.get_latest_snapshot()
    return {
        "status": "success",
        "gpu": snapshot.gpu.model_dump(),
        "cpu": snapshot.cpu.model_dump(),
        "timestamp": snapshot.timestamp,
        "is_paused": svc.is_paused
    }

@app.get("/api/telemetry/history")
def get_telemetry_history_endpoint():
    from backend.telemetry import get_telemetry_service
    svc = get_telemetry_service()
    return {"status": "success", "history": svc.get_history()}

@app.post("/api/telemetry/pause")
def set_telemetry_pause_endpoint(payload: TelemetryPauseRequest):
    from backend.telemetry import get_telemetry_service
    svc = get_telemetry_service()
    svc.set_paused(payload.paused)
    return {"status": "success", "is_paused": svc.is_paused}


# ==============================================================================
# AVATAR LOCAL ASSET DISCOVERY, VALIDATION, AND CONTROLLER ENDPOINTS
# ==============================================================================

class AvatarValidateRequest(BaseModel):
    path: str

class AvatarAnalyzeRequest(BaseModel):
    path: str
    relativePath: Optional[str] = None

class AvatarPermissionsRequest(BaseModel):
    permissions: Dict[str, Any]
    userApproved: bool = True

class AvatarSimulateEventRequest(BaseModel):
    event: str
    data: Optional[Dict[str, Any]] = None

class AvatarConvertPreviewRequest(BaseModel):
    sourcePath: str

class AvatarConvertRequest(BaseModel):
    sourcePath: str
    userApproved: bool = True

class AvatarImportRequest(BaseModel):
    sourcePath: str
    targetName: Optional[str] = "MidPoly.fbx"
    userApproved: bool = True


@app.get("/api/avatar/discover")
def discover_avatar_assets_endpoint():
    """Discover all 3D assets in approved project directories."""
    from backend.avatar.avatar_discovery import get_avatar_discovery
    assets = get_avatar_discovery().discover_local_assets()
    return {"status": "success", "assets": assets}


@app.post("/api/avatar/validate")
def validate_avatar_asset_endpoint(req: AvatarValidateRequest):
    """Validate asset path against path traversal, remote URLs, and format rules."""
    from backend.avatar.avatar_discovery import get_avatar_discovery
    is_valid, err = get_avatar_discovery().validate_path_safety(req.path)
    return {"status": "success" if is_valid else "error", "isValid": is_valid, "error": err}


@app.post("/api/avatar/analyze")
def analyze_avatar_asset_endpoint(req: AvatarAnalyzeRequest):
    """Analyze local GLB/GLTF model structure, capabilities, and features."""
    from backend.avatar.avatar_analyzer import get_avatar_analyzer
    from backend.avatar.avatar_state import get_avatar_state_manager

    analyzer = get_avatar_analyzer()
    full_path = req.path
    if not os.path.isabs(full_path):
        full_path = os.path.join(config.BASE_DIR, full_path)

    rel_source = req.relativePath or os.path.relpath(full_path, config.BASE_DIR)
    manifest = analyzer.analyze_glb_file(full_path, rel_source)

    # Automatically set active asset in state manager
    get_avatar_state_manager().set_active_asset(
        asset_id=manifest["assetId"],
        manifest_path=f"assets/avatars/beckie/generated/avatar-manifest.json",
        runtime_path=manifest["runtimeFile"],
    )

    return {"status": "success", "manifest": manifest}


@app.get("/api/avatar/manifest")
def get_avatar_manifest_endpoint():
    """Return latest generated avatar manifest."""
    manifest_path = os.path.join(config.BASE_DIR, "assets", "avatars", "beckie", "generated", "avatar-manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            return {"status": "success", "manifest": json.load(f)}
    return {"status": "error", "message": "No avatar manifest generated yet."}


@app.get("/api/avatar/state")
def get_avatar_state_endpoint():
    """Return current avatar state and revocable user permissions."""
    from backend.avatar.avatar_state import get_avatar_state_manager
    state = get_avatar_state_manager().get_state()
    return {"status": "success", "state": state}


@app.post("/api/avatar/permissions")
def update_avatar_permissions_endpoint(req: AvatarPermissionsRequest):
    """Update avatar permissions with mandatory audit logging."""
    from backend.avatar.avatar_state import get_avatar_state_manager
    state = get_avatar_state_manager().update_permissions(req.permissions, user_approved=req.userApproved)
    return {"status": "success", "state": state}


@app.get("/api/avatar/audit")
def get_avatar_audit_endpoint(limit: int = 50):
    """Return local audit log entries."""
    from backend.avatar.avatar_audit import get_audit_logger
    entries = get_audit_logger().get_recent_entries(limit=limit)
    return {"status": "success", "entries": entries}


@app.post("/api/avatar/simulate-event")
def simulate_avatar_event_endpoint(req: AvatarSimulateEventRequest):
    """Emit an avatar event over WebSocket for testing and persona reactions."""
    from backend.avatar.avatar_event_publisher import get_avatar_event_publisher
    event = get_avatar_event_publisher().publish_event(req.event, req.data)
    return {"status": "success", "dispatched": event}


@app.get("/api/avatar/asset-file")
def get_avatar_asset_file_endpoint(path: str = Query(...)):
    """Safely stream local avatar GLB/GLTF file with strict path security."""
    from backend.avatar.avatar_discovery import get_avatar_discovery, APPROVED_DIRECTORIES
    is_valid, err = get_avatar_discovery().validate_path_safety(path)
    if not is_valid:
        raise HTTPException(status_code=400, detail=err)

    full_path = path if os.path.isabs(path) else os.path.join(config.BASE_DIR, path)
    full_path = os.path.normpath(full_path)

    # Verify inside approved directories
    is_approved = any(full_path.startswith(os.path.normpath(d)) for d in APPROVED_DIRECTORIES)
    if not is_approved:
        raise HTTPException(status_code=403, detail="Access denied: file not in approved asset folders")

    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Asset file not found")

    ext = os.path.splitext(full_path)[1].lower()
    media_type = "model/gltf-binary" if ext == ".glb" else "model/gltf+json" if ext == ".gltf" else "application/octet-stream"
    return FileResponse(full_path, media_type=media_type, filename=os.path.basename(full_path))


@app.get("/api/avatar/blender-status")
def get_blender_status_endpoint():
    """Detect Blender on host system."""
    from backend.avatar.blender_converter import get_blender_converter
    return get_blender_converter().detect_blender()


@app.post("/api/avatar/convert-preview")
def get_avatar_convert_preview_endpoint(req: AvatarConvertPreviewRequest):
    """Return conversion preview summary before headless conversion."""
    from backend.avatar.blender_converter import get_blender_converter
    try:
        preview = get_blender_converter().get_conversion_preview(req.sourcePath)
        return {"status": "success", "preview": preview}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/avatar/convert")
def convert_avatar_endpoint(req: AvatarConvertRequest):
    """Execute headless Blender conversion from FBX to GLB with explicit approval."""
    from backend.avatar.blender_converter import get_blender_converter
    try:
        report = get_blender_converter().convert_fbx(req.sourcePath)
        return {"status": "success", "report": report}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/avatar/import-file")
def import_avatar_file_endpoint(req: AvatarImportRequest):
    """Safely copy an approved local FBX asset into assets/avatars/beckie/source/ without altering original."""
    import shutil
    from backend.avatar.avatar_audit import get_audit_logger
    from backend.avatar.avatar_discovery import get_avatar_discovery

    is_valid, err = get_avatar_discovery().validate_path_safety(req.sourcePath)
    if not is_valid:
        raise HTTPException(status_code=400, detail=err)

    src_full = req.sourcePath if os.path.isabs(req.sourcePath) else os.path.join(config.BASE_DIR, req.sourcePath)
    src_full = os.path.normpath(src_full)

    if not os.path.isfile(src_full):
        raise HTTPException(status_code=404, detail="Source file not found")

    dest_dir = os.path.join(config.BASE_DIR, "assets", "avatars", "beckie", "source")
    os.makedirs(dest_dir, exist_ok=True)

    dest_name = req.targetName or os.path.basename(src_full)
    dest_full = os.path.join(dest_dir, dest_name)

    # Safe copy only if paths differ; never modify original
    if os.path.abspath(src_full) != os.path.abspath(dest_full):
        shutil.copy2(src_full, dest_full)

    rel_dest = os.path.relpath(dest_full, config.BASE_DIR).replace("\\", "/")

    get_audit_logger().log(
        action="IMPORT_APPROVED",
        source_file=rel_dest,
        details={
            "originalSource": src_full,
            "targetLocation": rel_dest,
            "sizeBytes": os.path.getsize(dest_full),
        },
        user_approved=req.userApproved,
    )

    return {"status": "success", "importedPath": rel_dest, "fileSize": os.path.getsize(dest_full)}


@app.get("/api/avatar/conversion-report")
def get_avatar_conversion_report_endpoint():
    """Return latest conversion-report.json."""
    from backend.avatar.blender_converter import get_blender_converter
    report = get_blender_converter().get_conversion_report()
    return {"status": "success", "report": report}


# Mount Static Web Interface at root
web_dir = os.path.join(config.BASE_DIR, "web")
if os.path.exists(web_dir):
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")

if __name__ == "__main__":
    import uvicorn
    import socket

    def find_free_port(default_port=8000):
        for port in [default_port, 8080, 8081, 8888]:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                res = sock.connect_ex(('127.0.0.1', port))
                if res != 0:
                    return port
        return default_port

    port = find_free_port(8000)

    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "192.168.X.X"

    print("\n" + "=" * 60)
    print("STARTING JARVIS FASTAPI SERVER & MOBILE DASHBOARD")
    print(f" -> On this PC:    http://localhost:{port}")
    print(f" -> On Mobile:     http://{local_ip}:{port}")
    print("=" * 60 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=port)


