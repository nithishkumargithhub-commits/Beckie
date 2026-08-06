# 🛠️ Jarvis — Technology Stack & Tools

## Languages

| Language | Version | Usage |
|---|---|---|
| **Python** | 3.10+ | Entire backend, AI, audio pipeline, GUI |
| **JavaScript** (ES6+) | — | Web/Mobile SPA client (`web/app.js`) |
| **HTML5** | — | Web UI shell (`web/index.html`) |
| **CSS3** | — | Glassmorphism web theme (`web/style.css`) |
| **YAML** | — | Docker Compose configuration |
| **Dockerfile** | — | Container image definition |
| **JSON** | — | To-do list persistence, OAuth tokens |
| **SQL (SQLite)** | — | Conversation history, reminders, auth |

---

## Core AI & ML

| Library | Version | Purpose |
|---|---|---|
| **google-genai** | ≥0.1.1 | Gemini 2.0 Flash — intent classification, code generation, web search, vision |
| **openwakeword** | ≥0.5.1 | ONNX-based wake word detection ("hey_jarvis") |
| **faster-whisper** | ≥1.0.0 | Local Whisper STT (base model, int8 quantized, CPU) |
| **edge-tts** | ≥6.1.0 | Microsoft Edge Neural TTS (en-US-ChristopherNeural) |
| **pyttsx3** | ≥2.90 | Offline SAPI5 TTS fallback |

---

## Audio

| Library | Version | Purpose |
|---|---|---|
| **pyaudio** | ≥0.2.14 | Microphone capture (PyAudio / PortAudio backend) |
| **sounddevice** | ≥0.4.6 | Alternative audio device enumeration |
| **numpy** | ≥1.26.0 | Audio resampling, RMS volume calculation, PCM manipulation |
| **wave** (stdlib) | — | Writing 16kHz mono WAV temp files |

---

## Web Framework

| Library | Version | Purpose |
|---|---|---|
| **fastapi** | ≥0.100.0 | REST API server + WebSocket server + static file hosting |
| **uvicorn** | ≥0.22.0 | ASGI server runtime |
| **python-multipart** | ≥0.0.6 | Form data parsing for FastAPI |
| **pydantic** | ≥2.0.0 | Intent schema validation, API request models |

---

## Google APIs

| Library | Version | Purpose |
|---|---|---|
| **google-api-python-client** | ≥2.0.0 | Google Calendar, Gmail, Tasks API clients |
| **google-auth-httplib2** | ≥0.1.0 | HTTP adapter for Google OAuth |
| **google-auth-oauthlib** | ≥1.0.0 | OAuth2 InstalledAppFlow for user authentication |

**OAuth Scopes Used:**
- `https://www.googleapis.com/auth/calendar.events`
- `https://www.googleapis.com/auth/tasks`
- `https://www.googleapis.com/auth/gmail.readonly`
- `https://www.googleapis.com/auth/gmail.send`

---

## Desktop GUI

| Library | Version | Purpose |
|---|---|---|
| **customtkinter** | ≥5.2.0 | Modern themed Tkinter widgets (dark mode, rounded corners) |
| **pystray** | ≥0.19.0 | System tray icon + context menu |
| **pillow** | ≥10.0.0 | Image generation for tray icon |

---

## System & OS

| Library | Version | Purpose |
|---|---|---|
| **psutil** | ≥5.9.0 | CPU, RAM, disk usage monitoring |
| **pycaw** | ≥2.0.1 | Windows Core Audio API for volume control |
| **screen-brightness-control** | ≥0.17.0 | Cross-platform display brightness adjustment |
| **pyperclip** | ≥1.8.2 | Clipboard read/write |
| **ctypes** (stdlib) | — | Win32 API: MCI audio, hotkey, mutex, workstation lock |
| **subprocess** (stdlib) | — | Launching applications, running generated code |
| **socket** (stdlib) | — | Single-instance socket server (port 54321) |
| **sqlite3** (stdlib) | — | Embedded database |
| **hashlib** (stdlib) | — | SHA-256 voice password hashing |
| **ast** (stdlib) | — | Code safety AST inspection |

---

## External Services

| Service | Protocol | Purpose |
|---|---|---|
| **Google Gemini API** | HTTPS REST | Intent classification, code gen, answers, vision |
| **Microsoft Edge TTS** | HTTPS (edge-tts) | Neural speech synthesis |
| **wttr.in** | HTTPS JSON | Weather lookup (no API key required) |
| **Google Calendar API** | OAuth2 REST | Reminder/event CRUD |
| **Gmail API** | OAuth2 REST | Read unread emails, send emails |
| **Google Tasks API** | OAuth2 REST | Task list management |
| **Home Assistant** | HTTP REST | Smart home device control |
| **Ollama** | HTTP localhost | Local LLM inference (llama3 / gemma2) |
| **YouTube** | Browser automation | Song/video playback (via webbrowser module) |

---

## Development & Infrastructure

| Tool | Purpose |
|---|---|
| **Docker** | Container image build |
| **Docker Compose** | Service orchestration with volume mounts |
| **python-dotenv** (manual) | `.env` file parsing (custom implementation in `config.py`) |
| **pytest** | Unit testing framework (implied by test files) |
| **PortAudio** (system lib) | Audio I/O backend for PyAudio |
| **ffmpeg** (system lib) | Audio codec support (Docker image) |
| **espeak** (system lib) | Fallback TTS engine (Docker image) |

---

## Config-Driven Behavior Summary

All key behavior is driven by environment variables loaded from `.env`:

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(required)* | Google Gemini API key |
| `WAKE_WORD` | `hey_jarvis` | openWakeWord model name |
| `WAKE_WORD_THRESHOLD` | `0.38` | Confidence threshold for activation |
| `MIC_GAIN` | `1.5` | Software microphone amplification |
| `WHISPER_MODEL` | `base` | Whisper model size (tiny/base/small) |
| `WHISPER_DEVICE` | `cpu` | Device for Whisper inference |
| `WHISPER_COMPUTE_TYPE` | `int8` | Quantization type |
| `WHISPER_LANGUAGE` | `en` | Transcription language |
| `JARVIS_API_KEY` | *(empty)* | REST API authentication key |
| `CODE_SANDBOX_ENABLED` | `True` | Enable AST safety check for generated code |
| `ENABLE_RAG_MEMORY` | `True` | Enable conversational memory retrieval |
| `ENABLE_WEB_SONGS` | `True` | Allow YouTube song playback |
| `CHROME_DEFAULT_EMAIL` | *(empty)* | Default Chrome profile for YouTube |
| `HASS_URL` | `http://localhost:8123` | Home Assistant URL |
| `HASS_TOKEN` | *(empty)* | Home Assistant long-lived access token |
