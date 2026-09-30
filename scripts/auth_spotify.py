"""
BECKIE - Automatic Spotify OAuth Authorization Server.

Starts a local HTTP server on port 8888, opens the browser to Spotify consent.
When Spotify redirects back, this server automatically captures the code,
exchanges it for tokens, stores it encrypted in core.token_store, and tests playback!
"""

import os
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import datetime

# Ensure line-buffered stdout
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config
from spotipy.oauth2 import SpotifyOAuth
import spotipy
from core.token_store import save_token, load_token

_PROVIDER = "spotify"
_ACCOUNT = "default"
PORT = 8888
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", f"http://127.0.0.1:{PORT}/callback")
SCOPES = "streaming user-read-playback-state user-modify-playback-state playlist-read-private playlist-read-collaborative user-library-read user-top-read user-read-recently-played"

auth_code = None

class SpotifyCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            html = """
            <html>
            <head>
                <title>BECKIE // Spotify Connected</title>
                <style>
                    body { background: #030716; color: #00B8FF; font-family: monospace; text-align: center; padding-top: 80px; }
                    .card { background: #061028; border: 1px solid #1677FF; padding: 40px; border-radius: 16px; display: inline-block; box-shadow: 0 0 30px rgba(0,184,255,0.3); }
                    h1 { color: #D7EEFF; margin-bottom: 10px; }
                    p { color: #6A92BA; font-size: 14px; }
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>BECKIE // SPOTIFY CONNECTED</h1>
                    <p>Authorization successful! You can close this tab and return to the BECKIE 3D HUD.</p>
                </div>
            </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
        else:
            error = params.get("error", ["Unknown error"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(f"Spotify Authorization Error: {error}".encode("utf-8"))

    def log_message(self, format, *args):
        pass  # Suppress default server log clutter

def main():
    print("=" * 64, flush=True)
    print("       BECKIE // AUTOMATIC SPOTIFY OAUTH AUTHORIZATION", flush=True)
    print("=" * 64, flush=True)

    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("[ERROR] SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET missing in .env!", flush=True)
        sys.exit(1)

    sp_oauth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=REDIRECT_URI,
        scope=SCOPES,
        open_browser=False
    )

    auth_url = sp_oauth.get_authorize_url()

    print(f"\n[1/3] Using Spotify Redirect URI: {REDIRECT_URI}", flush=True)
    print(f"[2/3] Starting local callback server on http://127.0.0.1:{PORT}/ ...", flush=True)
    
    server = HTTPServer(("127.0.0.1", PORT), SpotifyCallbackHandler)
    server.timeout = 180  # 3 minute timeout

    print(f"[3/3] Opening browser for Spotify authorization...", flush=True)
    print("\nAuthorization URL:\n" + auth_url + "\n", flush=True)

    try:
        webbrowser.open(auth_url)
    except Exception as ex:
        print(f"[NOTE] Please open the URL manually in your browser: {ex}", flush=True)

    print("Waiting for Spotify authorization redirect (click 'Agree' in browser)...", flush=True)

    while not auth_code:
        server.handle_request()

    server.server_close()

    if not auth_code:
        print("\n[ERROR] No authorization code received from Spotify.", flush=True)
        sys.exit(1)

    print(f"\n[OK] Received Spotify authorization code! Exchanging for token...", flush=True)

    try:
        token_info = sp_oauth.get_access_token(auth_code, as_dict=True, check_cache=False)
        if not token_info or "access_token" not in token_info:
            print("[ERROR] Failed to obtain access token from Spotify response.", flush=True)
            sys.exit(1)

        expires_at = None
        if token_info.get("expires_at"):
            ts = int(token_info["expires_at"])
            expires_at = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat()

        # Save to encrypted token store
        save_token(
            _PROVIDER,
            _ACCOUNT,
            token_info,
            scopes=token_info.get("scope"),
            expires_at=expires_at
        )

        tokens_file = os.path.join(config.BASE_DIR, "spotify_tokens.json")
        try:
            with open(tokens_file, "w", encoding="utf-8") as f:
                json.dump(token_info, f, indent=2)
            print("[SUCCESS] Spotify tokens saved permanently to spotify_tokens.json & encrypted DB!", flush=True)
        except Exception as ex:
            print(f"[WARNING] Could not write to spotify_tokens.json: {ex}", flush=True)

        # Verify by fetching current user and exact playlists
        sp = spotipy.Spotify(auth=token_info["access_token"])
        user = sp.current_user()
        print(f"[VERIFIED] Logged in as: {user.get('display_name')} (Email: {user.get('email', 'N/A')})", flush=True)
        
        try:
            pls = sp.current_user_playlists(limit=25)
            print(f"[VERIFIED] Found {pls.get('total', 0)} exact personal playlists:", flush=True)
            for p in pls.get("items", []):
                print(f"  • {p.get('name')} ({p.get('tracks', {}).get('total', 0)} tracks) - {p.get('uri')}", flush=True)
        except Exception as pl_err:
            print(f"[WARNING] Could not list playlists: {pl_err}", flush=True)

        print("\n" + "=" * 64, flush=True)
        print("  SPOTIFY CONNECTED! DASHBOARD CAN NOW LOAD YOUR EXACT PLAYLISTS.", flush=True)
        print("=" * 64, flush=True)

    except Exception as e:
        print(f"[ERROR] Failed during token exchange: {e}", flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
