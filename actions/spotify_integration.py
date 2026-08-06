import os
import json
import logging
import urllib.request
import urllib.parse
from typing import Tuple
import config

logger = logging.getLogger("VoiceAssistant.Spotify")

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")

def play_spotify_track(query: str) -> Tuple[bool, str]:
    """
    Plays track via Spotify desktop application or Web API.
    """
    clean_query = query.strip()
    if not clean_query:
        try:
            os.startfile("spotify:")
            return True, "Opening Spotify playback."
        except Exception:
            return False, "Could not open Spotify desktop client."

    encoded_query = urllib.parse.quote(clean_query)
    
    # 1. Attempt native URI protocol handler on Windows
    try:
        spotify_uri = f"spotify:search:{encoded_query}"
        logger.info(f"Opening Spotify URI protocol: {spotify_uri}")
        os.startfile(spotify_uri)
        return True, f"Searching and playing '{clean_query}' on Spotify."
    except Exception as e:
        logger.warning(f"Native Spotify URI launch failed: {e}")

    # 2. Fallback to web search url
    url = f"https://open.spotify.com/search/{encoded_query}"
    import webbrowser
    webbrowser.open(url)
    return True, f"Opened Spotify Web search for '{clean_query}'."
