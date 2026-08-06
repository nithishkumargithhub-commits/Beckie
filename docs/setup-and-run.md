# 🚀 Jarvis — Setup & Run Guide

## Prerequisites

| Requirement | Minimum Version | Notes |
|---|---|---|
| Python | 3.10+ | Required. 3.11 recommended. |
| pip | Latest | For package installation |
| Microphone | — | Required for voice activation |
| Speakers | — | Required for TTS output |
| Google Account | — | Optional: for Calendar, Gmail, Tasks |
| Gemini API Key | — | Free tier available at [aistudio.google.com](https://aistudio.google.com) |

---

## 1. Clone / Download the Project

```bash
# If using git:
git clone <your-repo-url>
cd jarvis

# Or just navigate to the extracted project folder
cd c:\Users\nithi\Downloads\jarvis
```

---

## 2. Set Up Python Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate it (Windows)
.venv\Scripts\activate

# Activate it (macOS / Linux)
source .venv/bin/activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

> **Note for Windows users:** If `pyaudio` fails to install, use:
> ```bash
> pip install pipwin
> pipwin install pyaudio
> ```

---

## 4. Configure the Environment

Create a `.env` file in the project root (copy from the template below):

```env
# REQUIRED — Google Gemini AI Key
GEMINI_API_KEY=your_gemini_api_key_here

# Wake Word (default: hey_jarvis)
WAKE_WORD=hey_jarvis
WAKE_WORD_THRESHOLD=0.38

# Microphone boost (increase if mic is quiet)
MIC_GAIN=1.5

# Speech Recognition (Whisper)
WHISPER_MODEL=base
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
WHISPER_LANGUAGE=en

# API Security (leave empty to disable auth on REST API)
JARVIS_API_KEY=

# Features
CODE_SANDBOX_ENABLED=True
ENABLE_RAG_MEMORY=True
ENABLE_WEB_SONGS=True

# Optional: Chrome profile for YouTube
CHROME_DEFAULT_EMAIL=

# Optional: Home Assistant
HASS_URL=http://localhost:8123
HASS_TOKEN=
```

---

## 5. Download AI Models

Run the model pre-download script once before first launch:

```bash
python download_models.py
```

This downloads the openWakeWord ONNX model weights.

> Faster-Whisper model weights are downloaded automatically on first transcription.

---

## 6. (Optional) Set Up Google Services

To use Calendar, Gmail, or Google Tasks:

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project → Enable **Calendar API**, **Gmail API**, **Tasks API**
3. Configure OAuth Consent Screen → Add your Google account as test user
4. Create **OAuth 2.0 Credentials** → Desktop App → Download as `credentials.json`
5. Place `credentials.json` in the **project root** folder (alongside `main.py`)

On first use, a browser window will open for Google OAuth login. The token is cached in `token.json`.

---

## 7. Run Jarvis

### Option A — Windows One-Click Launch
```bat
jarvis.bat
```

### Option B — Python Direct

```bash
# Activate venv first
.venv\Scripts\activate

# Launch with GUI Dashboard (default on Windows)
python main.py

# Launch in headless mode (no GUI)
set HEADLESS=true
python main.py
```

### Option C — Run the Web/API Server Only

```bash
python server.py
```

Access the web dashboard at: `http://localhost:8000`
Access on mobile: `http://<your-pc-ip>:8000`

---

## 8. (Optional) Run with Docker

See [`docker.md`](./docker.md) for full Docker instructions.

Quick start:

```bash
# Set your Gemini key in the environment first
set GEMINI_API_KEY=your_key_here

docker-compose up --build
```

---

## Activating Jarvis

Once running, you can invoke Jarvis in three ways:

| Method | How |
|---|---|
| **Wake Word** | Say "Hey Jarvis" out loud |
| **Hotkey** | Press `Ctrl+Alt+J` (or fallback: `Ctrl+Shift+J`) |
| **GUI Input** | Type a command in the Dashboard or FloatingHUD input box |
| **Web UI** | Open `http://localhost:8000` and use the text input or mic button |
| **REST API** | `POST /api/command` with `{"command": "..."}` |

---

## Quick Test Commands

Once Jarvis is running, try these:

```
"Hey Jarvis"
  → "Open Chrome"
  → "What's the weather today?"
  → "Tell me a joke"
  → "Set a reminder for meeting at 3 PM"
  → "Generate a Python script that prints fibonacci numbers"
  → "What time is it?"
  → "Turn off my lights"
  → "Play some jazz music"
  → "Take a screenshot and tell me what's on my screen"
```

---

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run individual tests
python -m pytest tests/test_memory_rag.py -v
python -m pytest tests/test_security_auth.py -v
```

---

## Logs

Jarvis logs everything to:
- **Console** — real-time output
- **`assistant.log`** — rotating log file in project root
- **GUI Dashboard** — live scrollable log viewer in the app

---

## Common Issues & Fixes

| Issue | Fix |
|---|---|
| `pyaudio` not found | Install via `pipwin install pyaudio` on Windows |
| Mic stream fails to open | Check Windows Privacy > Microphone settings; allow Desktop Apps |
| `GEMINI_API_KEY not set` | Verify `.env` exists and key is correct |
| Wake word not detecting | Lower `WAKE_WORD_THRESHOLD` to `0.25` in `.env` |
| TTS sounds robotic | Check internet connection (Edge-TTS requires internet); pyttsx3 is the offline fallback |
| Google Calendar not working | Ensure `credentials.json` is in project root; re-run OAuth flow |
| Dashboard crashes immediately | Check if `customtkinter` is installed; try `pip install customtkinter` |
| Docker mic not working | Pass `/dev/snd` device in docker-compose.yml (already configured) |
