# 🔄 Jarvis — End-to-End Request Flow

This document describes the full lifecycle of a user command, from audio capture to spoken response.

---

## Voice Command Flow (Primary Path)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 1 — AUDIO CAPTURE                                                      │
│                                                                               │
│  PyAudio continuously reads 80ms PCM chunks from the microphone.             │
│  If stream is not 16kHz mono, chunks are resampled via linear interpolation.  │
│  MIC_GAIN (default 1.5×) is applied to boost quiet microphones.              │
└────────────────────────────────┬────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 2 — WAKE WORD DETECTION                                                │
│                                                                               │
│  openWakeWord (ONNX inference) predicts a confidence score for each chunk.   │
│  If score ≥ WAKE_WORD_THRESHOLD (default 0.38), activation fires.            │
│  Default wake word: "hey_jarvis"                                             │
│                                                                               │
│  Alternatively, the global hotkey (Ctrl+Alt+J) sets hotkey_event             │
│  which is polled at the top of the main loop.                                │
└────────────────────────────────┬────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 3 — COMMAND RECORDING                                                  │
│                                                                               │
│  Speaker says "Yes?" as an activation acknowledgment.                        │
│  assistant_state → "listening"                                               │
│  5 seconds of audio are recorded from the mic stream into a temp WAV file.  │
│  Stale buffered audio is flushed before recording begins.                    │
└────────────────────────────────┬────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 4 — SPEECH-TO-TEXT (STT)                                               │
│                                                                               │
│  Transcriber.transcribe(wav_file) is called.                                 │
│  Primary: faster-whisper (base model, VAD filter, beam_size=5)              │
│  Fallback: SpeechRecognition → Google Web Speech API                         │
│  Hallucination filtering removes common Whisper artifacts.                   │
│  Returns raw text string of the spoken command.                              │
└────────────────────────────────┬────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 5 — DICTATION MODE CHECK                                               │
│                                                                               │
│  If config.DICTATION_MODE is True:                                           │
│    → Text is appended to voice_notes.txt                                    │
│    → If "stop dictating" detected, exits dictation mode                      │
│  Otherwise → continue to classification                                      │
└────────────────────────────────┬────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 6 — INTENT CLASSIFICATION (NLU)                                        │
│                                                                               │
│  IntentClassifier.classify(text) sends the transcript to                     │
│  Google Gemini (gemini-2.0-flash) with a structured output schema.           │
│                                                                               │
│  Returns IntentAnalysis Pydantic model:                                      │
│    {                                                                          │
│      intent: IntentEnum  (e.g. "open_app")                                  │
│      target: str         (e.g. "chrome")                                     │
│      params: Dict        (e.g. {"action": "shutdown"})                       │
│    }                                                                          │
│                                                                               │
│  Fallback: keyword-based rule matching if no Gemini API key.                 │
└────────────────────────────────┬────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 7 — ACTION DISPATCH                                                    │
│                                                                               │
│  _process_command_inner() routes intent to its action handler:               │
│                                                                               │
│  IntentEnum.OPEN_APP         → actions/system_ops.open_app()                │
│  IntentEnum.GENERATE_CODE    → actions/code_agent.generate_code()           │
│  IntentEnum.WEB_SEARCH       → Gemini API / Ollama fallback                 │
│  IntentEnum.SET_REMINDER     → actions/reminders.create_calendar_reminder() │
│  IntentEnum.CHECK_EMAIL      → actions/google_services.check_unread_emails()│
│  IntentEnum.SCREEN_VISION    → actions/vision.analyze_screen_with_ai()      │
│  IntentEnum.SMART_HOME       → actions/smart_home.control_smart_device()    │
│  ... (35 total intents)                                                       │
│                                                                               │
│  Destructive actions (shutdown, code run) require a voice/GUI confirmation.  │
└────────────────────────────────┬────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 8 — TEXT-TO-SPEECH (TTS)                                               │
│                                                                               │
│  speaker.speak(response_text) enqueues text to the TTS worker thread.        │
│  Primary: Edge-TTS (en-US-ChristopherNeural) renders MP3 to temp file.      │
│  Playback: Windows WinMM MCI API (zero-subprocess, fast)                    │
│  Fallback: pyttsx3 with SAPI5 voices                                         │
│  assistant_state → "speaking" → "idle"                                       │
└────────────────────────────────┬────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 9 — PERSISTENCE                                                        │
│                                                                               │
│  database.log_interaction(user_query, response, intent) saves to SQLite.    │
│  Conversation history is browsable from the GUI and via /api/command.        │
│  RAG memory can optionally be stored for preference learning.                │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## API Command Flow (REST Path)

```
External Client / Web UI
        │
        │  POST /api/command
        │  {"command": "play some music"}
        │
        ▼
   server.py (FastAPI)
        │
        │  verify_api_key() ← checks X-API-Key header or ?api_key= query param
        │
        ▼
  _process_command_inner(text, stream=None, speak=fake_speak)
        │
        │  Intent classification → action dispatch (same as voice path)
        │  speak() calls go to a list collector instead of the TTS engine
        │
        ▼
  Returns: { success, intent, response }
        │
        ▼
  database.save_interaction() → SQLite
```

---

## Code Generation Flow (GENERATE_CODE Intent)

```
User: "Generate a Python script that sorts a list of numbers"
        │
        ▼
  generate_code(prompt)
        │  Sends prompt to Gemini with strict "output only ```python...```" instructions
        │  Extracts code block with regex
        │  Saves to generated_code.py
        ▼
  inspect_code_safety(code)
        │  AST-walks the code
        │  Checks for dangerous imports: os, sys, subprocess, socket, etc.
        │  Checks for dangerous calls: eval, exec, open, getattr, etc.
        ▼
  If unsafe → warns user, asks confirmation
  If safe   → asks user to run
        │
        ▼
  execute_generated_code()
        │  subprocess.run([python, generated_code.py], timeout=30)
        │  Captures stdout + stderr
        ▼
  If fails → fix_code_with_ai(prompt, failed_code, error_msg)
        │  Sends error context back to Gemini for a fix
        │  Retries up to 2 times
        ▼
  Speaks the last output line (if < 100 chars)
```

---

## Reminder Daemon Flow

```
startup
  │
  ▼
reminder_daemon.start()
  │  Spawns ReminderDaemonThread (daemon=True)
  │
  ▼  Every 30 seconds:
check_and_notify_due_reminders()
  │  SELECT pending reminders WHERE scheduled_time <= NOW
  │
  ├─▶ speaker.speak("Reminder Alert: {title}")   ← TTS callback
  │
  └─▶ ws_manager.broadcast({event: "reminder_due", ...})  ← WebSocket push
        │
        ▼
      Web / Mobile client receives real-time notification toast
```

---

## Memory RAG Flow

```
User asks: "What music do I like?"
        │
        ▼
  query_memories("What music do I like?", top_k=2)
        │  Tokenizes query → TF-IDF vector
        │  Loads all rag_memories rows from SQLite
        │  Computes cosine similarity for each memory
        │  Returns top-2 memories with similarity > 0.15
        ▼
  memory_context = "[User Context: user likes jazz; user uses Spotify]"
        │
        ▼
  Gemini prompt = "{memory_context}\nAnswer: {query}"
```

---

## Startup Sequence

```
main()
  1. check_single_instance_and_restore()    ← Socket check on port 54321
  2. Named Mutex guard (Windows)
  3. database.init_db()                     ← Create/migrate SQLite tables
  4. reminder_daemon.start()                ← Start 30s polling thread
  5. Speaker()                              ← Init TTS worker thread
  6. IntentClassifier()                     ← Init Gemini client
  7. if is_headless:
       Thread → run_voice_assistant_loop()
       Block on while True / KeyboardInterrupt
     else:
       DashboardApp()                       ← Init CustomTkinter GUI
       Thread → run_hotkey_listener()
       Thread → run_voice_assistant_loop()
       app.mainloop()                       ← Block on GUI event loop
```
