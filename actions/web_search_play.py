import os
import json
import logging
import urllib
import urllib.parse
import subprocess
from typing import Tuple, Optional
import config

logger = logging.getLogger("VoiceAssistant.WebSearchPlay")

def get_chrome_profile_directory(email: str) -> str:
    """
    Parses Google Chrome's Local State file to find the profile directory
    associated with the given email address.
    """
    if not email:
        return "Default"
        
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if not local_app_data:
        return "Default"
        
    local_state_path = os.path.join(local_app_data, "Google", "Chrome", "User Data", "Local State")
    if os.path.exists(local_state_path):
        try:
            with open(local_state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            profile_info = data.get("profile", {}).get("info_cache", {})
            for prof_dir, info in profile_info.items():
                user_name = info.get("user_name", "")
                if user_name.lower().strip() == email.lower().strip():
                    logger.info(f"Matched email {email} to Chrome profile directory: {prof_dir}")
                    return prof_dir
        except Exception as e:
            logger.error(f"Error reading Chrome Local State file: {e}")
            
    return "Default"

def find_chrome_executable() -> Optional[str]:
    """
    Finds the Google Chrome executable path on the Windows system.
    """
    # 1. Try registry lookup from system_ops if possible
    try:
        from actions.system_ops import get_app_path_from_registry
        path = get_app_path_from_registry("chrome")
        if path and os.path.exists(path):
            return path
    except Exception:
        pass
        
    # 2. Try standard locations
    for path in [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe")
    ]:
        if os.path.exists(path):
            return path
            
    return None

def play_song_or_video(query: str, platform: str = "youtube") -> Tuple[bool, str]:
    """
    Searches for a song/video on Spotify, YouTube, or Google/Web and opens it in Spotify App/Chrome
    under the configured user profile.
    """
    if not getattr(config, "ENABLE_WEB_SONGS", True):
        return False, "Song playback is currently disabled in settings."

    query_clean = query.strip()
    if not query_clean:
        return False, "Please specify a song or video name to search."

    # Normalize platform string
    platform_lower = str(platform).lower().strip()

    # Detect platform explicitly mentioned inside query string if present
    lower_query = query_clean.lower()
    if "spotify" in lower_query:
        platform_lower = "spotify"
    elif "youtube" in lower_query:
        platform_lower = "youtube"
    elif any(p in lower_query for p in ["web", "google"]):
        platform_lower = "web"

    # Remove filler prefixes
    for prefix in [
        "play song ", "play music ", "play video ", "play track ", "play audio ",
        "play spotify ", "play youtube ", "play google ", "play web ", "play ",
        "search for ", "search ", "find song ", "find music ", "find video ", "find "
    ]:
        if lower_query.startswith(prefix):
            query_clean = query_clean[len(prefix):].strip()
            lower_query = query_clean.lower()
            break

    # Remove filler suffixes (e.g. "on spotify", "in spotify", "on youtube", "on google", "on web")
    for suffix in [
        " on spotify", " in spotify", " spotify",
        " on youtube", " in youtube", " youtube",
        " on google", " in google", " google",
        " on web", " on the web", " web"
    ]:
        if lower_query.endswith(suffix):
            query_clean = query_clean[:-len(suffix)].strip()
            lower_query = query_clean.lower()
            break

    # If query became empty after removing filler words (e.g. user said "play spotify")
    if not query_clean or lower_query in ["spotify", "youtube", "google", "web"]:
        if platform_lower == "spotify":
            try:
                os.startfile("spotify:")
                return True, "Opening Spotify app."
            except Exception:
                pass
            url = "https://open.spotify.com"
            action_name = "Spotify Web"
        elif platform_lower == "youtube":
            url = "https://www.youtube.com"
            action_name = "YouTube"
        else:
            url = "https://www.google.com"
            action_name = "Google"

        email = getattr(config, "CHROME_DEFAULT_EMAIL", "nithishnithishkumar371@gmail.com")
        profile_dir = get_chrome_profile_directory(email)
        chrome_path = find_chrome_executable()
        if chrome_path:
            try:
                subprocess.Popen([chrome_path, f"--profile-directory={profile_dir}", url])
                return True, f"Opening {action_name} in Chrome."
            except Exception:
                pass
        import webbrowser
        webbrowser.open(url)
        return True, f"Opening {action_name} in default browser."

    encoded_query = urllib.parse.quote(query_clean)
    encoded_query_plus = urllib.parse.quote_plus(query_clean)

    if platform_lower == "spotify":
        # 1. Try launching native Spotify app via URI protocol handler
        try:
            spotify_uri = f"spotify:search:{encoded_query}"
            logger.info(f"Attempting to launch Spotify app via protocol: {spotify_uri}")
            os.startfile(spotify_uri)
            msg = f"Playing '{query_clean}' on Spotify."
            return True, msg
        except Exception as e:
            logger.warning(f"Failed to open Spotify URI handler ({e}). Falling back to Spotify Web.")

        # 2. Fallback to Spotify Web search in Chrome/browser
        url = f"https://open.spotify.com/search/{encoded_query}"
        action_name = "Spotify"
    elif platform_lower == "youtube":
        url = f"https://www.youtube.com/results?search_query={encoded_query_plus}"
        action_name = "YouTube"
    else:
        url = f"https://www.google.com/search?q={encoded_query_plus}"
        action_name = "Google"

    # Get Chrome Profile Directory
    email = getattr(config, "CHROME_DEFAULT_EMAIL", "nithishnithishkumar371@gmail.com")
    profile_dir = get_chrome_profile_directory(email)

    chrome_path = find_chrome_executable()
    if chrome_path:
        try:
            cmd = [chrome_path, f"--profile-directory={profile_dir}", url]
            subprocess.Popen(cmd)
            msg = f"Opening {action_name} to search for '{query_clean}' using profile linked to {email}."
            logger.info(msg)
            return True, msg
        except Exception as e:
            logger.error(f"Failed to launch Chrome: {e}")

    try:
        import webbrowser
        webbrowser.open(url)
        msg = f"Opening search for '{query_clean}' on {action_name} in default browser."
        logger.info(msg)
        return True, msg
    except Exception as e:
        return False, f"Failed to open browser: {e}"
