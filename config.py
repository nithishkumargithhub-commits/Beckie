import os

# Assistant Details
ASSISTANT_NAME = "Jarvis"
VERSION = "0.1.0"

# Mutable state to control listening at runtime
ASSISTANT_ENABLED = True
DICTATION_MODE = False

# Lively Visualizer States
ASSISTANT_STATE = "idle"  # "idle", "listening", "processing", "speaking"
CURRENT_VOLUME = 0.0       # Live amplitude volume level

# Path configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ACTIONS_DIR = os.path.join(BASE_DIR, "actions")
STT_DIR = os.path.join(BASE_DIR, "stt")
TTS_DIR = os.path.join(BASE_DIR, "tts")
IDENTITY_DIR = os.path.join(BASE_DIR, "identity")

# Load environment variables from .env file if it exists in the project root
env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

# Dynamic Wake Word Settings
WAKE_WORDS = [os.getenv("WAKE_WORD", "hey_jarvis")]

# Dynamic Threshold Settings
try:
    WAKE_WORD_THRESHOLD = float(os.getenv("WAKE_WORD_THRESHOLD", "0.38"))
except ValueError:
    WAKE_WORD_THRESHOLD = 0.38

# Microphone gain multiplier
try:
    MIC_GAIN = float(os.getenv("MIC_GAIN", "1.5"))
except ValueError:
    MIC_GAIN = 1.5

# Speech-to-Text Settings (faster-whisper)
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "en")

# Gemini API Settings
GEMINI_MODEL = "gemini-2.0-flash"

# Security & API Settings
JARVIS_API_KEY = os.getenv("JARVIS_API_KEY", "")
CODE_SANDBOX_ENABLED = os.getenv("CODE_SANDBOX_ENABLED", "True").lower() == "true"
ENABLE_RAG_MEMORY = os.getenv("ENABLE_RAG_MEMORY", "True").lower() == "true"

# Web & YouTube Settings
ENABLE_WEB_SONGS = os.getenv("ENABLE_WEB_SONGS", "True").lower() == "true"
CHROME_DEFAULT_EMAIL = os.getenv("CHROME_DEFAULT_EMAIL", "")

# Text-to-Speech Settings
TTS_RATE = 175  # Speed of speech (words per minute)
TTS_VOLUME = 1.0  # Volume (0.0 to 1.0)

def save_env_var(key: str, val: str):
    """
    Saves or updates a variable in the local .env file and updates os.environ in memory.
    """
    os.environ[key] = str(val)
    lines = []
    found = False
    
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line_strip = line.strip()
                if line_strip and not line_strip.startswith("#") and "=" in line_strip:
                    k, v = line_strip.split("=", 1)
                    if k.strip() == key:
                        lines.append(f"{key}={val}\n")
                        found = True
                    else:
                        lines.append(line)
                else:
                    lines.append(line)
                    
    if not found:
        lines.append(f"{key}={val}\n")
        
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
