import os
import sys
import logging
import asyncio
from typing import List, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
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

# Event Loop Threadsafe Broadcast Helper for ReminderDaemon
def broadcast_daemon_notification(payload: dict):
    """Callback function registered with reminder_daemon to broadcast WebSocket alerts."""
    try:
        if main_loop and main_loop.is_running():
            asyncio.run_coroutine_threadsafe(ws_manager.broadcast(payload), main_loop)
    except Exception as e:
        logger.warning(f"Could not dispatch async broadcast: {e}")

# Register WebSocket broadcast callback with reminder daemon
reminder_daemon.register_callback(broadcast_daemon_notification)
reminder_daemon.start()


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


