"""
JARVIS – Spotify playback control via Spotipy.

Scopes (all three required for full playback control)
------------------------------------------------------
  streaming                       – required for Web Playback SDK (browser)
  user-read-playback-state        – read current track / device info
  user-modify-playback-state      – play, pause, skip, volume, seek

⚠️  Spotify Premium required
-----------------------------
  The Spotify Web API playback control endpoints are only available to
  Premium subscribers. Free accounts will receive a 403 Forbidden error
  from the API. Beckie will communicate this limitation to the user when
  it is detected.

Setup
-----
  Set these in your .env file (or OS environment):
    SPOTIFY_CLIENT_ID=<your_client_id>
    SPOTIFY_CLIENT_SECRET=<your_client_secret>
    SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback   (must match Spotify dashboard)

  On first run an OAuth browser window opens. The token is cached encrypted
  inside the SQLCipher database via core.token_store.

Usage
-----
  from actions.spotify_secure import play, pause, skip, volume, now_playing
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional, Tuple

import config
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from core.token_store import load_token, save_token

logger = logging.getLogger("Jarvis.Actions.Spotify")


# ---------------------------------------------------------------------------
# OAuth configuration
# ---------------------------------------------------------------------------

_PROVIDER = "spotify"
_ACCOUNT = "default"

SPOTIFY_SCOPES = " ".join([
    "streaming",
    "user-read-playback-state",
    "user-modify-playback-state",
    "playlist-read-private",
    "playlist-read-collaborative",
    "user-library-read",
    "user-top-read",
    "user-read-recently-played"
])

_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")



_TOKENS_FILE = os.path.join(config.BASE_DIR, "spotify_tokens.json")


# ---------------------------------------------------------------------------
# Spotipy client factory (with encrypted DB and permanent JSON file caching)
# ---------------------------------------------------------------------------

class _PersistentCacheHandler(spotipy.cache_handler.CacheHandler):
    """
    Dual-layer persistent token cache:
    1. Loads from workspace spotify_tokens.json if present.
    2. Falls back to encrypted SQLCipher DB (core.token_store).
    3. Automatically updates both on refresh, guaranteeing permanent auth persistence.
    """
    def get_cached_token(self):
        if os.path.exists(_TOKENS_FILE):
            try:
                with open(_TOKENS_FILE, "r", encoding="utf-8") as f:
                    tok = json.load(f)
                    if tok and "access_token" in tok:
                        return tok
            except Exception:
                pass

        tok = load_token(_PROVIDER, _ACCOUNT)
        if tok and "access_token" in tok:
            try:
                with open(_TOKENS_FILE, "w", encoding="utf-8") as f:
                    json.dump(tok, f, indent=2)
            except Exception:
                pass
            return tok
        return None

    def save_token_to_cache(self, token_info):
        try:
            with open(_TOKENS_FILE, "w", encoding="utf-8") as f:
                json.dump(token_info, f, indent=2)
        except Exception:
            pass

        expires_at = None
        if token_info.get("expires_at"):
            import datetime
            ts = int(token_info["expires_at"])
            expires_at = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat()
        save_token(
            _PROVIDER,
            _ACCOUNT,
            token_info,
            scopes=token_info.get("scope"),
            expires_at=expires_at,
        )


def _get_spotify():
    """
    Build an authenticated Spotipy client using the permanent token cache.
    Automatically and silently refreshes expired tokens via refresh_token.
    Guaranteed NEVER to block on console or interactive input.
    """
    import spotipy
    import time
    from spotipy.oauth2 import SpotifyOAuth

    client_id = os.getenv("SPOTIFY_CLIENT_ID", "")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        raise EnvironmentError(
            "SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set in your .env file."
        )

    cache = _PersistentCacheHandler()
    token_info = cache.get_cached_token()
    if not token_info or "access_token" not in token_info:
        raise PermissionError(
            "Spotify account not authenticated. Please authorize your Spotify account first."
        )

    # Check if token is expired or expiring in the next 60 seconds
    now = int(time.time())
    expires_at = token_info.get("expires_at", 0)
    if (expires_at - now < 60) and token_info.get("refresh_token"):
        try:
            sp_oauth = SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=_REDIRECT_URI,
                scope=SPOTIFY_SCOPES,
                cache_handler=cache,
                open_browser=False
            )
            refreshed = sp_oauth.refresh_access_token(token_info["refresh_token"])
            if refreshed and "access_token" in refreshed:
                token_info = refreshed
                cache.save_token_to_cache(token_info)
        except Exception as e:
            logger.warning(f"Failed silent refresh of Spotify token: {e}")

    return spotipy.Spotify(auth=token_info["access_token"])


def _handle_spotify_error(exc: Exception) -> Tuple[bool, str]:
    """Translate Spotipy exceptions into user-friendly messages."""
    msg = str(exc)
    if isinstance(exc, PermissionError):
        return False, msg
    if "403" in msg or "PREMIUM_REQUIRED" in msg.upper():
        return False, (
            "Spotify playback control requires a Premium subscription. "
            "Please upgrade your Spotify account to use this feature."
        )
    if "404" in msg or "NO_ACTIVE_DEVICE" in msg.upper():
        return False, (
            "No active Spotify device found. "
            "Please open the Spotify app on a device first."
        )
    return False, f"Spotify error: {exc}"


def launch_app() -> Tuple[bool, str]:
    """Launches the Spotify desktop application or opens the web player."""
    try:
        os.startfile("spotify:")
        return True, "Launched Spotify Desktop App."
    except Exception:
        import webbrowser
        webbrowser.open("https://open.spotify.com")
        return True, "Opened Spotify Web Player."


_PREFERENCES_FILE = os.path.join(config.BASE_DIR, "spotify_preferences.json")


def get_preferences() -> dict:
    """Returns the user's exact preferences: top artists, top tracks, recently played, and favorite genres."""
    if not is_spotify_authenticated():
        return {
            "top_artists": [],
            "top_tracks": [],
            "recently_played": [],
            "favorite_genres": [],
            "needs_scope_grant": False
        }

    try:
        sp = _get_spotify()
        top_artists = []
        genres_set = set()
        try:
            art_res = sp.current_user_top_artists(limit=10, time_range="medium_term")
            for a in art_res.get("items", []):
                top_artists.append({
                    "name": a.get("name"),
                    "genres": a.get("genres", []),
                    "image": a.get("images", [{}])[0].get("url", "") if a.get("images") else "",
                    "uri": a.get("uri")
                })
                for g in a.get("genres", []):
                    genres_set.add(g.title())
        except Exception as e:
            logger.debug(f"Top artists query: {e}")

        top_tracks = []
        try:
            trk_res = sp.current_user_top_tracks(limit=10, time_range="medium_term")
            for t in trk_res.get("items", []):
                top_tracks.append({
                    "name": t.get("name"),
                    "artist": t.get("artists", [{}])[0].get("name", "Unknown Artist"),
                    "uri": t.get("uri"),
                    "album": t.get("album", {}).get("name", "")
                })
        except Exception as e:
            logger.debug(f"Top tracks query: {e}")

        recently_played = []
        try:
            rec_res = sp.current_user_recently_played(limit=10)
            for item in rec_res.get("items", []):
                t = item.get("track", {})
                recently_played.append({
                    "name": t.get("name"),
                    "artist": t.get("artists", [{}])[0].get("name", "Unknown Artist"),
                    "uri": t.get("uri"),
                    "played_at": item.get("played_at")
                })
        except Exception as e:
            logger.debug(f"Recently played query: {e}")

        fav_genres = sorted(list(genres_set))[:8]
        return {
            "top_artists": top_artists,
            "top_tracks": top_tracks,
            "recently_played": recently_played,
            "favorite_genres": fav_genres,
            "needs_scope_grant": False
        }
    except Exception as e:
        logger.error(f"Error fetching exact user preferences: {e}")
        needs_scope = "scope" in str(e).lower() or "403" in str(e)
        return {
            "top_artists": [],
            "top_tracks": [],
            "recently_played": [],
            "favorite_genres": [],
            "needs_scope_grant": needs_scope
        }


def get_playlists() -> list:
    """Returns the user's exact personal playlists from their authenticated Spotify account."""
    if not is_spotify_authenticated():
        return []

    try:
        sp = _get_spotify()
        res = sp.current_user_playlists(limit=50)
        items = res.get("items", [])
        exact_playlists = []
        for p in items:
            images = p.get("images", [])
            img_url = images[0].get("url") if images else ""
            exact_playlists.append({
                "id": p.get("id"),
                "name": p.get("name", "Untitled Playlist"),
                "curator": p.get("owner", {}).get("display_name", "Spotify User"),
                "uri": p.get("uri", ""),
                "track_count": p.get("tracks", {}).get("total", 0),
                "tag": "MY PLAYLIST",
                "image": img_url,
                "public": bool(p.get("public", False))
            })
        return exact_playlists
    except Exception as e:
        logger.error(f"Error fetching exact user playlists: {e}")
        # If scope missing, check if user has custom added playlists
        prefs = {}
        if os.path.exists(_PREFERENCES_FILE):
            try:
                with open(_PREFERENCES_FILE, "r", encoding="utf-8") as f:
                    prefs = json.load(f)
            except Exception:
                pass
        return prefs.get("user_added_playlists", [])


def add_custom_playlist(name: str, uri_or_url: str, tag: str = "MY PLAYLIST") -> Tuple[bool, str]:
    """Allows pinning an exact user playlist link or URI."""
    prefs = {}
    if os.path.exists(_PREFERENCES_FILE):
        try:
            with open(_PREFERENCES_FILE, "r", encoding="utf-8") as f:
                prefs = json.load(f)
        except Exception:
            pass

    playlists = prefs.get("user_added_playlists", [])

    clean_uri = uri_or_url.strip()
    if "open.spotify.com/playlist/" in clean_uri:
        part = clean_uri.split("/playlist/")[1].split("?")[0]
        clean_uri = f"spotify:playlist:{part}"

    new_entry = {
        "id": f"custom_{len(playlists)+1}",
        "name": name.strip() or "My Playlist",
        "curator": "My Account",
        "uri": clean_uri,
        "track_count": 0,
        "tag": tag.upper(),
        "image": ""
    }
    playlists.insert(0, new_entry)
    prefs["user_added_playlists"] = playlists
    try:
        with open(_PREFERENCES_FILE, "w", encoding="utf-8") as f:
            json.dump(prefs, f, indent=2)
    except Exception:
        pass
    return True, f"Playlist '{name}' added successfully."


def play_uri(uri: str) -> Tuple[bool, str]:
    """Plays a playlist, album, or track URI directly."""
    try:
        sp = _get_spotify()
        devices = []
        try:
            devices = sp.devices().get("devices", [])
        except Exception:
            pass

        if devices:
            try:
                if "playlist" in uri or "album" in uri:
                    sp.start_playback(context_uri=uri)
                else:
                    sp.start_playback(uris=[uri])
                return True, f"Started playback of {uri} on Spotify."
            except Exception:
                pass

        try:
            os.startfile(uri)
            return True, f"Launched {uri} in Spotify Desktop App."
        except Exception:
            pass

        if uri.startswith("spotify:playlist:"):
            pl_id = uri.split(":")[-1]
            import webbrowser
            webbrowser.open(f"https://open.spotify.com/playlist/{pl_id}")
            return True, "Opened playlist in Spotify Web."

        return False, f"Could not launch playback for {uri}."
    except Exception as exc:
        return _handle_spotify_error(exc)


# ---------------------------------------------------------------------------
# Playback controls
# ---------------------------------------------------------------------------

def play(query: Optional[str] = None) -> Tuple[bool, str]:
    """
    Resume playback or search and play a track/artist/album or playlist.
    query: search term or Spotify URI. If None, resumes current playback.
    Automatically launches the Spotify desktop app or web player if no device is active.
    """
    if query and (query.startswith("spotify:") or "open.spotify.com" in query):
        return play_uri(query)

    try:
        sp = _get_spotify()
        if query:
            results = sp.search(q=query, limit=1, type="track")
            tracks = results.get("tracks", {}).get("items", [])
            if not tracks:
                return False, f"No Spotify track found for '{query}'."
            track = tracks[0]
            uri = track["uri"]
            name = track["name"]
            artist = track["artists"][0]["name"]


            # Check if active devices exist
            try:
                devices = sp.devices().get("devices", [])
            except Exception:
                devices = []

            if devices:
                try:
                    sp.start_playback(uris=[uri])
                    return True, f"Playing '{name}' by {artist} on Spotify."
                except Exception:
                    pass

            # If no active device or playback call failed, launch in Spotify app directly on Windows!
            try:
                os.startfile(uri)
                return True, f"Playing '{name}' by {artist} in Spotify App."
            except Exception:
                pass

            # Fallback to web player link
            track_id = track.get("id")
            if track_id:
                import webbrowser
                webbrowser.open(f"https://open.spotify.com/track/{track_id}")
                return True, f"Playing '{name}' by {artist} on Spotify Web."

            return False, f"Could not launch Spotify playback for '{name}'."
        else:
            try:
                sp.start_playback()
                return True, "Resumed Spotify playback."
            except Exception as e:
                # If no active device, open the app
                try:
                    os.startfile("spotify:")
                    return True, "Opened Spotify app to resume playback."
                except Exception:
                    return _handle_spotify_error(e)
    except Exception as exc:
        return _handle_spotify_error(exc)



def pause() -> Tuple[bool, str]:
    """Pause current Spotify playback."""
    try:
        sp = _get_spotify()
        sp.pause_playback()
        return True, "Spotify playback paused."
    except Exception as exc:
        return _handle_spotify_error(exc)


def skip_next() -> Tuple[bool, str]:
    """Skip to next track."""
    try:
        sp = _get_spotify()
        sp.next_track()
        return True, "Skipped to next track on Spotify."
    except Exception as exc:
        return _handle_spotify_error(exc)


def skip_previous() -> Tuple[bool, str]:
    """Go back to previous track."""
    try:
        sp = _get_spotify()
        sp.previous_track()
        return True, "Going back to previous track on Spotify."
    except Exception as exc:
        return _handle_spotify_error(exc)


def set_volume(percent: int) -> Tuple[bool, str]:
    """Set Spotify playback volume (0–100)."""
    try:
        sp = _get_spotify()
        vol = max(0, min(100, percent))
        sp.volume(vol)
        return True, f"Spotify volume set to {vol}%."
    except Exception as exc:
        return _handle_spotify_error(exc)


def now_playing() -> Tuple[bool, str]:
    """Return info about the currently playing track."""
    try:
        sp = _get_spotify()
        current = sp.current_playback()
        if not current or not current.get("is_playing"):
            return True, "Nothing is currently playing on Spotify."
        item = current.get("item", {})
        name = item.get("name", "Unknown")
        artist = item.get("artists", [{}])[0].get("name", "Unknown Artist")
        album = item.get("album", {}).get("name", "")
        progress_ms = current.get("progress_ms", 0)
        duration_ms = item.get("duration_ms", 1)
        pct = int(progress_ms / duration_ms * 100)
        return True, f"Now playing: '{name}' by {artist} from '{album}' ({pct}% through)."
    except Exception as exc:
        return _handle_spotify_error(exc)


def is_spotify_authenticated() -> bool:
    """Checks whether a cached Spotify token exists in JSON file or DB without blocking on stdin."""
    if os.path.exists(_TOKENS_FILE):
        try:
            with open(_TOKENS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data and "access_token" in data:
                    return True
        except Exception:
            pass
    try:
        token = load_token(_PROVIDER, _ACCOUNT)
        return bool(token and "access_token" in token)
    except Exception:
        return False



def get_current_track_data() -> dict:
    """Return structured JSON data for the HUD holographic mini-player."""
    if not is_spotify_authenticated():
        return {
            "is_active": False,
            "is_playing": False,
            "requires_auth": True,
            "connected": False
        }
    try:
        sp = _get_spotify()
        current = sp.current_playback()
        if not current:
            return {
                "is_active": False,
                "is_playing": False,
                "requires_auth": False,
                "connected": True,
                "title": "Playback Idle",
                "artist": "Spotify Connected",
                "album": "Ready to Stream"
            }
        item = current.get("item") or {}
        album = item.get("album") or {}
        images = album.get("images") or []
        album_art = images[0]["url"] if images else ""
        return {
            "is_active": True,
            "is_playing": bool(current.get("is_playing", False)),
            "title": item.get("name", "Unknown Track"),
            "artist": item.get("artists", [{}])[0].get("name", "Unknown Artist"),
            "album": album.get("name", ""),
            "album_art": album_art,
            "progress_ms": current.get("progress_ms", 0),
            "duration_ms": item.get("duration_ms", 0),
            "requires_auth": False,
            "connected": True
        }
    except Exception as e:
        return {
            "is_active": False,
            "is_playing": False,
            "requires_auth": False,
            "connected": is_spotify_authenticated(),
            "error": str(e),
            "title": "Spotify Standby",
            "artist": "Device Offline"
        }



def get_auth_url(redirect_uri: Optional[str] = None) -> str:
    """Generates the Spotify OAuth authorize URL."""
    from spotipy.oauth2 import SpotifyOAuth
    client_id = os.getenv("SPOTIFY_CLIENT_ID", "")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "")
    uri = redirect_uri or _REDIRECT_URI
    sp_oauth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=uri,
        scope=SPOTIFY_SCOPES,
        open_browser=False
    )
    return sp_oauth.get_authorize_url()


def exchange_code_for_token(code_or_url: str, redirect_uri: Optional[str] = None) -> Tuple[bool, str]:
    """
    Exchanges authorization code or full callback URL for access & refresh tokens,
    then saves to the encrypted SQLCipher token store.
    """
    import datetime
    from urllib.parse import urlparse, parse_qs
    from spotipy.oauth2 import SpotifyOAuth
    import spotipy

    client_id = os.getenv("SPOTIFY_CLIENT_ID", "")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return False, "SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET missing in .env"

    uri = redirect_uri or _REDIRECT_URI
    code = code_or_url.strip()
    if "code=" in code:
        parsed = urlparse(code)
        params = parse_qs(parsed.query)
        if "code" in params:
            code = params["code"][0]

    sp_oauth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=uri,
        scope=SPOTIFY_SCOPES,
        open_browser=False
    )

    try:
        token_info = sp_oauth.get_access_token(code, as_dict=True, check_cache=False)
        if not token_info or "access_token" not in token_info:
            return False, "Spotify returned empty access token."

        expires_at = None
        if token_info.get("expires_at"):
            ts = int(token_info["expires_at"])
            expires_at = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat()

        save_token(
            _PROVIDER,
            _ACCOUNT,
            token_info,
            scopes=token_info.get("scope"),
            expires_at=expires_at
        )

        try:
            _PersistentCacheHandler().save_token_to_cache(token_info)
        except Exception:
            pass

        sp = spotipy.Spotify(auth=token_info["access_token"])
        user = sp.current_user()
        name = user.get("display_name") or user.get("id") or "User"
        return True, f"Spotify connected successfully as '{name}'!"
    except Exception as e:
        logger.error(f"Error exchanging Spotify code: {e}")
        return False, f"Failed to exchange code: {e}"



