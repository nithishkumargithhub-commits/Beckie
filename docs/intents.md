# 🎙️ Jarvis — Supported Intents Reference

Jarvis supports **35 intents** classified by Google Gemini AI. Below is the complete reference for each intent, including what triggers it, what parameters are extracted, and what action is performed.

---

## Application Management

### `open_app`
Opens a desktop application.
- **Trigger:** "Open Chrome", "Launch Notepad", "Start Spotify"
- **Target:** Application name (e.g., `chrome`, `notepad`)
- **Action:** `actions/system_ops.open_app()`

### `close_app`
Closes/terminates a running application.
- **Trigger:** "Close Chrome", "Exit Notepad", "Kill Spotify"
- **Target:** Application name
- **Action:** `actions/system_ops.close_app()` → falls back to `manage_window("close")`

### `open_folder`
Opens a folder in File Explorer.
- **Trigger:** "Open Downloads folder", "Show my Documents"
- **Target:** Folder name or path
- **Action:** `actions/system_ops.open_folder()`

---

## System Operations

### `system_op`
Performs OS-level power/session actions.
- **Trigger:** "Lock my computer", "Shut down", "Restart", "Sign out", "Cancel shutdown"
- **Params:** `action` → one of `lock`, `shutdown`, `restart`, `signout`, `cancel shutdown`
- **Action:** `lock_workstation()`, `shutdown_system()`, `restart_system()`, `signout_system()`, `abort_shutdown()`
- **⚠️ Confirmation required** for shutdown, restart, sign-out

### `set_volume`
Adjusts system audio volume.
- **Trigger:** "Set volume to 50%", "Turn up the volume", "Mute"
- **Target:** `up`, `down`, `mute`, `unmute`, or a percentage
- **Action:** `actions/system_ops.change_volume()` → `actions/os_adapter.set_volume()`

### `set_brightness`
Adjusts screen brightness.
- **Trigger:** "Set brightness to 80%", "Dim the screen", "Brighten my screen"
- **Target:** `up`, `down`, or a percentage
- **Action:** `actions/system_ops.change_brightness()` → `actions/os_adapter.set_brightness()`

### `window_manage`
Manages the foreground window.
- **Trigger:** "Minimize this window", "Maximize", "Close this window"
- **Target:** `minimize`, `maximize`, `close`, `restore`
- **Action:** `actions/window_manager.manage_window()`

### `media_control`
Controls system media playback.
- **Trigger:** "Pause music", "Next song", "Play", "Previous track"
- **Target:** `play`, `pause`, `next`, `previous`, `stop`
- **Action:** `actions/media_control.control_media()` (Win32 `SendInput` key events)

---

## Productivity

### `todo_add`
Adds a task to the local to-do list.
- **Trigger:** "Add buy groceries to my to-do list"
- **Target:** Task description
- **Action:** `actions/todo.add_todo_task()` → saves to `todo_list.json`

### `todo_list`
Lists all pending to-do tasks.
- **Trigger:** "What's on my to-do list?", "Show my tasks"
- **Action:** `actions/todo.list_todo_tasks()`

### `todo_complete`
Marks a task as complete.
- **Trigger:** "Mark buy groceries as done", "Complete task 2"
- **Target:** Task name or number
- **Action:** `actions/todo.complete_todo_task()`

### `todo_clear`
Clears all completed tasks.
- **Trigger:** "Clear my to-do list"
- **Action:** `actions/todo.clear_todo_list()`

### `note_dictate`
Enables voice dictation mode / appends to voice notes.
- **Trigger:** "Start dictating", "Take a note: ..."
- **Target:** `start` to begin dictation; subsequent commands are saved to `voice_notes.txt`
- **Exit:** "Stop dictating"
- **Action:** `config.DICTATION_MODE = True` / `actions/notes.append_to_dictation()`

### `timer_alarm`
Sets a countdown timer or manages a stopwatch.
- **Trigger:** "Set a timer for 10 minutes", "Start stopwatch", "Stop stopwatch"
- **Target:** Duration string (e.g., "10 minutes", "1 hour 30 minutes")
- **Params:** `type` → `stopwatch` if stopwatch
- **Action:** `actions/timer_alarm.set_countdown_timer()` / `handle_stopwatch()`

---

## Reminders & Google Integration

### `set_reminder`
Creates a reminder on Google Calendar.
- **Trigger:** "Remind me to take medicine at 9 PM", "Set a meeting reminder for Friday 3 PM"
- **Target:** Reminder description
- **Params:** `datetime` → ISO 8601 datetime string
- **Action:** `actions/reminders.create_calendar_reminder()` (requires `credentials.json`)

### `list_reminders`
Lists upcoming Google Calendar reminders.
- **Trigger:** "What are my reminders?", "Show my calendar"
- **Action:** `actions/reminders.list_calendar_reminders()`

### `check_email`
Checks unread Gmail messages.
- **Trigger:** "Check my emails", "Any new emails?", "Read my inbox"
- **Action:** `actions/google_services.check_unread_emails()`

### `send_email`
Sends an email via Gmail.
- **Trigger:** "Send an email to john@example.com about the meeting"
- **Target:** Recipient email
- **Params:** `to`, `subject`, `body`
- **Action:** `actions/google_services.send_email()`

### `google_task_add`
Adds a task to Google Tasks.
- **Trigger:** "Add finish report to my Google Tasks"
- **Target:** Task title
- **Action:** `actions/google_services.add_google_task()`

### `google_task_list`
Lists Google Tasks.
- **Trigger:** "Show my Google Tasks", "What tasks do I have in Google?"
- **Action:** `actions/google_services.list_google_tasks()`

### `google_task_complete`
Marks a Google Task as complete.
- **Trigger:** "Mark finish report as done in Google Tasks"
- **Target:** Task title
- **Action:** `actions/google_services.complete_google_task()`

---

## AI & Information

### `web_search`
Answers a question using Gemini AI (with optional Google Search grounding) or local Ollama fallback.
- **Trigger:** "What is quantum computing?", "Search for latest news about AI", "What time is sunrise?"
- **Target:** Query text
- **Action:** Gemini API → Ollama fallback; injects RAG memory context
- **Note:** Uses `google_search` tool for explicit web search keywords ("search for", "google", "look up", etc.)

### `generate_code`
Generates Python code using Gemini AI.
- **Trigger:** "Generate a Python script to sort a list", "Write code to scrape weather data"
- **Target:** Code description / user prompt
- **Action:** `actions/code_agent.generate_code()` → `inspect_code_safety()` → `execute_generated_code()` → auto-fix retry loop
- **⚠️ Confirmation required** before execution

### `run_code`
Runs an existing Python file.
- **Trigger:** "Run the file myScript.py"
- **Target:** File path
- **Action:** `subprocess.run([python, file_path], timeout=30)`
- **⚠️ Confirmation required**

### `screen_vision`
Captures a screenshot and analyzes it with Gemini multimodal.
- **Trigger:** "What's on my screen?", "Describe my screen", "Read the text on screen"
- **Target:** Optional analysis instruction
- **Action:** `actions/vision.analyze_screen_with_ai()`

### `clipboard_op`
Reads clipboard and processes with Gemini AI.
- **Trigger:** "Explain what's in my clipboard", "Translate my clipboard", "Fix the code I copied"
- **Target:** Action type (`explain`, `translate`, `fix`, `summarize`)
- **Action:** `actions/clipboard_assistant.process_clipboard_action()`

---

## Entertainment & Media

### `tell_joke`
Tells a random joke.
- **Trigger:** "Tell me a joke", "Say something funny"
- **Action:** `actions/jokes.get_random_joke()`

### `play_song`
Plays a song or video on YouTube or Spotify.
- **Trigger:** "Play Bohemian Rhapsody", "Play some jazz on Spotify"
- **Target:** Song/artist/query
- **Params:** `platform` → `youtube` or `spotify`
- **Action:** `actions/web_search_play.play_song_or_video()`

---

## Smart Home & IoT

### `smart_home`
Controls smart home devices via Home Assistant.
- **Trigger:** "Turn on the lights", "Turn off the fan", "Enable AC"
- **Target:** Device type or user utterance
- **Action:** `actions/smart_home.handle_smart_home_command()` → `control_smart_device(entity_id, action)`
- **Requires:** `HASS_URL` and `HASS_TOKEN` in `.env`; simulates if token not set

---

## Weather

### `get_weather`
Fetches current weather for a location.
- **Trigger:** "What's the weather?", "Weather in Tokyo", "Is it going to rain?"
- **Target:** City name (uses current location if empty)
- **Action:** `actions/weather.get_weather()` → hits `wttr.in` JSON API

---

## Security & Data

### `set_password`
Sets, changes, or disables the voice password guard.
- **Trigger:** "Set a voice password", "Change my password", "Disable voice password"
- **Params:** `action` → `set`, `change`, `disable`
- **Action:** `database.set_voice_password()` / `delete_voice_password()`
- **Note:** Password is SHA-256 hashed; spoken digits are normalized for fuzzy matching

### `pull_database`
Retrieves conversation history from SQLite (password-protected if set).
- **Trigger:** "Show my conversation history", "Search my history for weather"
- **Target:** Optional search query
- **Action:** `database.get_recent_history()` / `database.search_history()`

---

## Identity

### `introduce_self`
Jarvis introduces itself.
- **Trigger:** "Who are you?", "Introduce yourself", "What can you do?"
- **Action:** `identity/introduce.get_introduction()`

---

## Automation

### `run_macro`
Runs a preset multi-step automation macro.
- **Trigger:** "Run work mode macro", "Start presentation setup"
- **Target:** Macro name
- **Action:** `actions/macros.run_preset_macro()`

---

## File Search

### `search_file`
Searches for files on the computer.
- **Trigger:** "Find files named report", "Search for PDF files in Documents"
- **Target:** File name / query
- **Action:** `actions/file_search.search_files()` (uses Windows Search / Everything)

---

## System Monitoring

### `system_health`
Reports CPU, RAM, and disk usage.
- **Trigger:** "How's my system doing?", "Check system health", "CPU usage?"
- **Action:** `actions/system_health.get_system_health()` via `psutil`

---

## Unknown

### `unknown`
Fallback for unrecognized commands.
- **Behavior:** Speaks: "I transcribed: '{text}', but I couldn't understand the command intent."
