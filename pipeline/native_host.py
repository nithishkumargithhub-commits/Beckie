"""
JARVIS – Chrome Native Messaging Host.

Protocol: JSON-RPC 2.0 over stdin/stdout with Chrome's 4-byte length-prefix framing.

Message format (Chrome native messaging):
  [4 bytes little-endian length][UTF-8 JSON payload]

JSON-RPC Request:
  { "jsonrpc": "2.0", "id": <int>, "method": <str>, "params": <obj> }

JSON-RPC Response (success):
  { "jsonrpc": "2.0", "id": <int>, "result": <any> }

JSON-RPC Response (error):
  { "jsonrpc": "2.0", "id": <int>, "error": { "code": <int>, "message": <str> } }

Supported methods
-----------------
  ping                          → { "pong": true }
  gmail.unread                  → { "emails": [...] }
  calendar.upcoming             → { "events": [...] }
  spotify.play     { query? }   → { "message": str }
  spotify.pause                 → { "message": str }
  spotify.skip                  → { "message": str }
  spotify.volume   { percent }  → { "message": str }
  spotify.now_playing           → { "message": str }
  page.summarise   { text, url }→ { "summary": str }

Registration (Windows)
-----------------------
  Run: python -m pipeline.native_host --register
  This writes the required registry key and manifest JSON.
"""

from __future__ import annotations

import json
import logging
import os
import struct
import sys
from typing import Any, Dict

logger = logging.getLogger("Jarvis.NativeHost")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,  # stdout is reserved for Chrome framing
)

# ---------------------------------------------------------------------------
# Chrome native messaging framing
# ---------------------------------------------------------------------------

def _read_message() -> Dict[str, Any]:
    """Read one Chrome-framed message from stdin."""
    raw_len = sys.stdin.buffer.read(4)
    if len(raw_len) < 4:
        raise EOFError("stdin closed")
    msg_len = struct.unpack("<I", raw_len)[0]
    payload = sys.stdin.buffer.read(msg_len)
    return json.loads(payload.decode("utf-8"))


def _send_message(obj: Dict[str, Any]) -> None:
    """Write one Chrome-framed message to stdout."""
    encoded = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("<I", len(encoded)))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def _ok(msg_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _err(msg_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


# ---------------------------------------------------------------------------
# RPC method dispatch
# ---------------------------------------------------------------------------

def _dispatch(method: str, params: Dict[str, Any]) -> Any:
    """Route a JSON-RPC method to the appropriate Jarvis action."""

    # ── Ping ─────────────────────────────────────────────────────────────────
    if method == "ping":
        return {"pong": True, "version": "1.0.0"}

    # ── Gmail ─────────────────────────────────────────────────────────────────
    elif method == "gmail.unread":
        from actions.google_secure import check_unread_emails_secure
        ok, msg = check_unread_emails_secure(max_results=params.get("max_results", 5))
        if not ok:
            raise RuntimeError(msg)
        return {"message": msg}

    # ── Calendar ──────────────────────────────────────────────────────────────
    elif method == "calendar.upcoming":
        from actions.google_secure import get_upcoming_events
        ok, msg = get_upcoming_events(max_results=params.get("max_results", 5))
        if not ok:
            raise RuntimeError(msg)
        return {"message": msg}

    # ── Spotify ───────────────────────────────────────────────────────────────
    elif method == "spotify.play":
        from actions.spotify_integration import play
        ok, msg = play(params.get("query"))
        if not ok:
            raise RuntimeError(msg)
        return {"message": msg}

    elif method == "spotify.pause":
        from actions.spotify_integration import pause
        ok, msg = pause()
        if not ok:
            raise RuntimeError(msg)
        return {"message": msg}

    elif method == "spotify.skip":
        from actions.spotify_integration import skip_next
        ok, msg = skip_next()
        if not ok:
            raise RuntimeError(msg)
        return {"message": msg}

    elif method == "spotify.volume":
        from actions.spotify_integration import set_volume
        pct = int(params.get("percent", 50))
        ok, msg = set_volume(pct)
        if not ok:
            raise RuntimeError(msg)
        return {"message": msg}

    elif method == "spotify.now_playing":
        from actions.spotify_integration import now_playing
        ok, msg = now_playing()
        if not ok:
            raise RuntimeError(msg)
        return {"message": msg}

    # ── Page summarisation (text passed from extension) ───────────────────────
    elif method == "page.summarise":
        text = params.get("text", "")
        url = params.get("url", "")
        if not text:
            return {"summary": "No page text provided."}
        # Simple extraction — plug in LLM summariser if desired
        words = text.split()
        snippet = " ".join(words[:80]) + ("…" if len(words) > 80 else "")
        return {"summary": f"Page at {url}: {snippet}"}

    else:
        raise NotImplementedError(f"Unknown method: {method}")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run_host() -> None:
    """Block and serve JSON-RPC requests from Chrome until stdin closes."""
    logger.info("Beckie native messaging host started (PID %d)", os.getpid())

    # Add project root to path so imports work
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    while True:
        try:
            request = _read_message()
        except (EOFError, struct.error):
            logger.info("Chrome disconnected – shutting down native host")
            break

        msg_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params") or {}

        logger.info("RPC ← method=%s id=%s", method, msg_id)

        try:
            result = _dispatch(method, params)
            response = _ok(msg_id, result)
        except NotImplementedError as exc:
            response = _err(msg_id, -32601, str(exc))
        except Exception as exc:
            logger.error("RPC error for method=%s: %s", method, exc)
            response = _err(msg_id, -32000, str(exc))

        _send_message(response)
        logger.info("RPC → id=%s ok=%s", msg_id, "error" not in response)


# ---------------------------------------------------------------------------
# Registration helper (Windows registry + NMH manifest)
# ---------------------------------------------------------------------------

def register_native_host() -> None:
    """
    Write the Chrome native messaging host manifest and register it in the
    Windows registry so Chrome can find it.

    Run once after installation:
        python -m pipeline.native_host --register
    """
    import winreg

    host_name = "com.beckie.jarvis"
    script_path = os.path.abspath(__file__)
    # Use the same Python that is running this script
    python_exe = sys.executable

    # The wrapper batch script is more reliable for Chrome (no PATH issues)
    bat_path = os.path.join(os.path.dirname(script_path), "native_host_launcher.bat")
    with open(bat_path, "w") as f:
        f.write(f'@echo off\n"{python_exe}" "{script_path}" --run\n')

    manifest = {
        "name": host_name,
        "description": "Beckie (Jarvis) native messaging bridge",
        "path": bat_path,
        "type": "stdio",
        "allowed_origins": [],  # Populated after loading extension – see README
    }

    manifest_path = os.path.join(os.path.dirname(script_path), "com.beckie.jarvis.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    reg_key = rf"Software\Google\Chrome\NativeMessagingHosts\{host_name}"
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, reg_key) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, manifest_path)
        print(f"✓ Registered native host '{host_name}' in HKCU registry")
        print(f"  Manifest: {manifest_path}")
        print(f"  Launcher: {bat_path}")
        print()
        print("Next step: Load the chrome_extension/ folder in Chrome (Developer Mode)")
        print("Then copy the extension ID into allowed_origins in the manifest JSON.")
    except Exception as exc:
        print(f"✗ Registry write failed: {exc}")
        raise


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--register" in sys.argv:
        register_native_host()
    elif "--run" in sys.argv or True:
        run_host()
