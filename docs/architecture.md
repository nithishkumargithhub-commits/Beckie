# 🏗️ Jarvis — System Architecture

## Overview

Jarvis is a **multi-layered voice assistant** built entirely in Python. It is designed with a modular monolith architecture where each capability lives in its own module within the `actions/` directory. A central orchestrator (`main.py`) receives audio input, classifies it using Google Gemini AI, and dispatches to the right action handler.

---

## Top-Level Directory Layout

```
jarvis/
├── main.py                  # Core orchestrator, wake-word loop, intent dispatcher
├── server.py                # FastAPI REST + WebSocket server (web/mobile interface)
├── config.py                # Central config, .env loader, mutable state flags
├── download_models.py       # Pre-downloads AI model weights at build time
├── jarvis.bat               # Windows one-click launcher
├── Dockerfile               # Container image definition
├── docker-compose.yml       # Docker Compose service definition
├── requirements.txt         # Python package dependencies
├── jarvis.db                # SQLite persistent store (auto-created)
├── todo_list.json           # Local JSON to-do list persistence
├── voice_notes.txt          # Dictation mode output file
│
├── stt/                     # Speech-to-Text layer
│   └── transcriber.py       # faster-whisper / SpeechRecognition adapter
│
├── tts/                     # Text-to-Speech layer
│   └── speaker.py           # Edge-TTS (Neural) + pyttsx3 fallback speaker
│
├── intent/                  # NLU / Intent Classification
│   └── classifier.py        # Gemini-powered structured intent parser (Pydantic)
│
├── actions/                 # Action Handlers (one per capability)
│   ├── system_ops.py        # App open/close, shutdown, volume, brightness
│   ├── os_adapter.py        # Cross-platform OS primitives (win/mac/linux)
│   ├── code_agent.py        # AI code generation, AST safety inspection, execution
│   ├── database.py          # SQLite ORM: history, reminders, auth, RAG
│   ├── memory_rag.py        # TF-IDF cosine similarity memory retrieval
│   ├── google_services.py   # Google Calendar, Gmail, Tasks (OAuth2)
│   ├── reminders.py         # Reminder creation and listing (Google Calendar)
│   ├── reminder_daemon.py   # Background thread polling for due reminders
│   ├── weather.py           # Weather lookup via wttr.in
│   ├── web_search_play.py   # Gemini search + YouTube play via browser
│   ├── todo.py              # JSON to-do list CRUD
│   ├── jokes.py             # Random joke fetcher
│   ├── media_control.py     # System media keys (play/pause/next)
│   ├── window_manager.py    # Window minimize/maximize/close via Win32
│   ├── clipboard_assistant.py # Clipboard read + Gemini explain/translate/fix
│   ├── file_search.py       # Windows Everything / native file search
│   ├── smart_home.py        # Home Assistant REST API integration
│   ├── local_llm.py         # Ollama local LLM fallback
│   ├── vision.py            # Screenshot + Gemini multimodal screen analysis
│   ├── macros.py            # Preset multi-step automation macros
│   ├── timer_alarm.py       # Countdown timers and stopwatch
│   ├── notes.py             # Dictation / voice note appender
│   ├── system_health.py     # CPU/RAM/disk health report via psutil
│   ├── spotify_integration.py # Spotify playback via browser automation
│   └── macros.py            # Voice macro runner
│
├── gui/                     # Desktop GUI
│   └── dashboard.py         # CustomTkinter dashboard + FloatingHUD + SystemTray
│
├── identity/                # Persona
│   └── introduce.py         # Self-introduction response generator
│
├── web/                     # Web / Mobile UI (served by FastAPI)
│   ├── index.html           # Single-page app shell
│   ├── app.js               # WebSocket client, API calls, UI logic
│   └── style.css            # Glassmorphism dark theme CSS
│
└── tests/                   # Unit tests
    ├── test_memory_rag.py
    ├── test_security_auth.py
    ├── test_smart_home.py
    └── test_speaker.py
```

---

## Component Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACES                             │
│  ┌───────────────┐  ┌──────────────────────┐  ┌─────────────────┐ │
│  │  Voice / Mic  │  │  Desktop GUI (CTk)   │  │  Web / Mobile   │ │
│  │  Wake Word    │  │  Dashboard + HUD     │  │  (FastAPI SPA)  │ │
│  └──────┬────────┘  └──────────┬───────────┘  └────────┬────────┘ │
└─────────┼──────────────────────┼─────────────────────────┼────────┘
           │                      │                          │
           ▼                      ▼                          ▼ REST/WS
┌──────────────────────────────────────────────────────────────────┐
│                       CORE ORCHESTRATOR                           │
│                         main.py                                   │
│  ┌────────────────┐   ┌───────────────┐   ┌──────────────────┐   │
│  │  STT Layer     │   │  Intent Layer │   │  TTS Layer       │   │
│  │  transcriber   │──▶│  classifier   │   │  speaker (Edge)  │   │
│  │  (Whisper)     │   │  (Gemini AI)  │   │  + pyttsx3       │   │
│  └────────────────┘   └──────┬────────┘   └──────────────────┘   │
└──────────────────────────────┼───────────────────────────────────┘
                                │
               ┌────────────────▼──────────────────────────┐
               │          ACTION DISPATCHER                 │
               │   _process_command_inner()  in main.py     │
               └────────────────┬──────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────────────────┐
        │                       │                                    │
        ▼                       ▼                                    ▼
┌──────────────┐   ┌──────────────────────┐          ┌─────────────────────┐
│  System Ops  │   │  Cloud / Integrations│          │  Local Intelligence  │
│  system_ops  │   │  google_services     │          │  memory_rag          │
│  os_adapter  │   │  weather             │          │  local_llm (Ollama)  │
│  window_mgr  │   │  web_search_play     │          │  code_agent (Gemini) │
│  media_ctrl  │   │  reminders           │          │  vision (screenshot) │
│  smart_home  │   │  todo                │          │  clipboard_assistant │
└──────┬───────┘   └──────────┬───────────┘          └──────────┬──────────┘
       │                       │                                  │
       └───────────────────────┴──────────────────────────────────┘
                                          │
                              ┌───────────▼───────────┐
                              │  PERSISTENCE LAYER    │
                              │  SQLite (jarvis.db)   │
                              │  ┌──────────────────┐ │
                              │  │ convo_history    │ │
                              │  │ reminders        │ │
                              │  │ auth_settings    │ │
                              │  │ rag_memories     │ │
                              │  └──────────────────┘ │
                              └───────────────────────┘
```

---

## Module Responsibilities

### `main.py` (Orchestrator)
The brain of Jarvis. Runs three concurrent threads:
1. **Wake Word Loop** — continuously reads audio, runs openWakeWord ONNX model
2. **Hotkey Listener** — monitors `Ctrl+Alt+J` global hotkey (Windows only)
3. **GUI Main Loop** — runs CustomTkinter dashboard on main thread

Exposes `_process_command_inner()` — the single function that maps an `IntentEnum` value to its action handler. This function is reused by `server.py` for API command processing.

### `config.py` (Global State)
Centralized runtime configuration. Loads `.env` on startup, exposes mutable state globals (`ASSISTANT_STATE`, `CURRENT_VOLUME`, `DICTATION_MODE`, `ASSISTANT_ENABLED`). Provides `save_env_var()` for persisting settings changes at runtime.

### `stt/transcriber.py` (Speech-to-Text)
Wraps **faster-whisper** with a graceful fallback to Google's `SpeechRecognition` library if Whisper fails. Filters common Whisper hallucinations (e.g., "thanks for watching"). Outputs plain text.

### `tts/speaker.py` (Text-to-Speech)
A threaded queue-based speaker. Primary engine is **Microsoft Edge Neural TTS** (via `edge-tts`). Fallback is **pyttsx3** (offline SAPI5 voices). Supports barge-in (instant stop) via WinMM MCI API calls.

### `intent/classifier.py` (NLU)
Uses **Google Gemini** (`gemini-2.0-flash`) with a structured output schema (`IntentAnalysis` Pydantic model) to map raw user text to one of **35 intents**. Falls back to keyword-based rule matching if no API key is available.

### `actions/database.py` (Persistence)
SQLite ORM managing four tables: `convo_history`, `auth_settings`, `reminders`, `rag_memories`. Includes SHA-256 voice password hashing and fuzzy spoken digit normalization for password matching.

### `actions/memory_rag.py` (Contextual Memory)
In-process TF-IDF cosine similarity retrieval over stored `rag_memories`. Injects relevant past context into Gemini prompts during `web_search` intent handling.

### `server.py` (API Server)
FastAPI application providing:
- `POST /api/command` — text command execution
- `GET /api/reminders` — reminder list
- `GET /api/status` — CPU/RAM and server metrics
- `WS /ws` — real-time WebSocket for reminder push notifications
- Static file serving of the `web/` SPA

### `gui/dashboard.py` (Desktop GUI)
CustomTkinter-based desktop application with:
- **DashboardApp** — main window with live log viewer, settings panel, quick-action buttons
- **FloatingHUD** — compact always-on-top window showing conversation and quick input
- **SystemTray** — pystray icon for minimizing to tray

---

## Threading Model

```
Main Thread:
  └── app.mainloop()          ← GUI event loop (CustomTkinter)

Daemon Threads:
  ├── run_voice_assistant_loop()   ← Audio capture + wake word detection
  ├── run_hotkey_listener()        ← Win32 global hotkey WM_HOTKEY loop
  ├── Speaker._speak_worker()      ← TTS queue consumer
  └── ReminderDaemon._run_loop()   ← 30s interval DB polling for due reminders
```

All cross-thread communication uses `threading.Event`, `queue.Queue`, and `config.*` mutable globals with `mic_lock` mutex guarding raw audio stream reads.

---

## Single-Instance Guard

On Windows, Jarvis uses a **dual guard**:
1. **Named Mutex** (`Global\JarvisVoiceAssistantMutex`) — prevents second process launch
2. **Socket Server** on port `54321` — receives `b'restore'` signals to bring GUI to front
