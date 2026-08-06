import os
import sqlite3
import logging
import hashlib
import re
from google import genai
import config

logger = logging.getLogger("VoiceAssistant.Database")

DB_PATH = os.path.join(config.BASE_DIR, "jarvis.db")

def init_db():
    """
    Initializes database tables.
    """
    logger.info("Initializing SQLite database...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS convo_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                user_query TEXT,
                assistant_response TEXT,
                is_important INTEGER DEFAULT 0
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auth_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                title TEXT,
                scheduled_time TEXT,
                status TEXT DEFAULT 'pending'
            );
        """)
        conn.commit()
        logger.info("Database tables initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}")
    finally:
        conn.close()

DIGIT_MAP = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"
}

def _normalize_phrase(phrase: str) -> str:
    """
    Normalizes a spoken phrase by converting to lowercase, mapping word digits, removing punctuation and whitespace.
    """
    cleaned = phrase.lower().strip()
    # Remove punctuation
    cleaned = re.sub(r'[^\w\s]', '', cleaned)
    words = cleaned.split()
    converted = [DIGIT_MAP.get(w, w) for w in words]
    # Compact string without spaces to neutralize STT word segmentation differences (e.g. "pass 123" vs "pass123")
    return "".join(converted)

def hash_password(password: str) -> str:
    """
    Returns SHA-256 hash of a string.
    """
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def is_password_set() -> bool:
    """
    Checks if a password hash is set in database.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT value FROM auth_settings WHERE key = 'password_hash'")
        row = cursor.fetchone()
        return row is not None and bool(row[0])
    except Exception as e:
        logger.error(f"Error checking if password is set: {e}")
        return False
    finally:
        conn.close()

def set_voice_password(password: str) -> bool:
    """
    Hashes and saves the voice password.
    """
    normalized = _normalize_phrase(password)
    hashed = hash_password(normalized)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR REPLACE INTO auth_settings (key, value) VALUES ('password_hash', ?)", (hashed,))
        conn.commit()
        logger.info("Voice password hash updated successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to save voice password: {e}")
        return False
    finally:
        conn.close()

def verify_voice_password(spoken: str) -> bool:
    """
    Normalizes and checks the spoken password against the stored hash.
    """
    normalized = _normalize_phrase(spoken)
    hashed = hash_password(normalized)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT value FROM auth_settings WHERE key = 'password_hash'")
        row = cursor.fetchone()
        if row:
            stored_hash = row[0]
            if stored_hash == hashed:
                return True
            # Secondary fallback: compare with spaces removed without word-to-digit conversion
            raw_compact = re.sub(r'[^\w]', '', spoken.lower())
            if stored_hash == hash_password(raw_compact):
                return True
        return False
    except Exception as e:
        logger.error(f"Failed to verify voice password: {e}")
        return False
    finally:
        conn.close()

def add_local_reminder(title: str, scheduled_time: str) -> bool:
    """
    Saves a reminder to SQLite database.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO reminders (title, scheduled_time) VALUES (?, ?)",
            (title, scheduled_time)
        )
        conn.commit()
        logger.info(f"Local reminder saved to database: '{title}' at {scheduled_time}")
        return True
    except Exception as e:
        logger.error(f"Failed to save local reminder: {e}")
        return False
    finally:
        conn.close()

def delete_voice_password() -> bool:
    """
    Deletes the voice password.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM auth_settings WHERE key = 'password_hash'")
        conn.commit()
        logger.info("Voice password deleted.")
        return True
    except Exception as e:
        logger.error(f"Failed to delete voice password: {e}")
        return False
    finally:
        conn.close()

def classify_importance(user_query: str, assistant_response: str, intent: str) -> int:
    """
    Classifies if the interaction is important (1) or unnecessary (0).
    Uses Gemini API if online, falls back to local rules if offline.
    """
    # 1. Fallback Heuristics for Unimportant System Actions
    unimportant_intents = {
        "set_volume", "set_brightness", "tell_joke", "get_weather", 
        "system_op", "open_app", "open_folder", "introduce_self"
    }
    if intent in unimportant_intents:
        logger.info(f"Local heuristic classified intent '{intent}' as UNNECESSARY.")
        return 0

    # 2. Try Gemini API Importance Classification
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            client = genai.Client(api_key=api_key)
            prompt = (
                "You are an information relevance classifier. Determine if the following conversation turn contains important information that should be saved for future reference (e.g. user notes, coding requests, facts, calendar reminders, todo tasks) "
                "or if it is unnecessary/transient system actions/jokes/greetings (e.g. changing volume, screen brightness, telling jokes, opening files/apps, trivial hello/hi, checking weather).\n\n"
                f"User: {user_query}\n"
                f"Assistant: {assistant_response}\n\n"
                "Output ONLY the word 'IMPORTANT' or 'UNNECESSARY'."
            )
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt
            )
            ans = response.text.strip().upper()
            logger.info(f"Gemini classified interaction as: {ans}")
            if "IMPORTANT" in ans:
                return 1
            return 0
        except Exception as e:
            logger.warning(f"Gemini importance classification failed: {e}. Falling back to default important.")

    # 3. Offline default for other intents (todo_add, set_reminder, generate_code, web_search, unknown)
    logger.info("Defaulting offline intent classification to IMPORTANT.")
    return 1

def prune_data():
    """
    Prunes the database:
    1. Deletes unimportant conversations immediately.
    2. Deletes all conversations older than 60 days.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # Delete unnecessary logs
        cursor.execute("DELETE FROM convo_history WHERE is_important = 0")
        deleted_unnecessary = cursor.rowcount
        
        # Delete old logs (60 days)
        cursor.execute("DELETE FROM convo_history WHERE timestamp < datetime('now', '-60 days')")
        deleted_old = cursor.rowcount
        
        if deleted_unnecessary > 0 or deleted_old > 0:
            logger.info(f"Database pruned: {deleted_unnecessary} unimportant entries, {deleted_old} old entries deleted.")
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to prune database: {e}")
    finally:
        conn.close()

def log_interaction(user_query: str, assistant_response: str, intent: str = "unknown"):
    """
    Logs user query and assistant response.
    Automatically classifies importance and prunes database.
    """
    if not user_query.strip() or not assistant_response.strip():
        return

    is_important = classify_importance(user_query, assistant_response, intent)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO convo_history (user_query, assistant_response, is_important) VALUES (?, ?, ?)",
            (user_query, assistant_response, is_important)
        )
        conn.commit()
        logger.info(f"Logged interaction. ID: {cursor.lastrowid}, Important: {is_important}")
    except Exception as e:
        logger.error(f"Failed to log interaction: {e}")
    finally:
        conn.close()
        
    # Prune database records automatically
    prune_data()

def search_history(query: str) -> list:
    """
    Searches the conversation history for records matching query.
    Returns list of dicts.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        like_query = f"%{query}%"
        cursor.execute(
            "SELECT timestamp, user_query, assistant_response FROM convo_history WHERE user_query LIKE ? OR assistant_response LIKE ? ORDER BY timestamp DESC",
            (like_query, like_query)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to search history: {e}")
        return []
    finally:
        conn.close()

def get_recent_history(limit: int = 5) -> list:
    """
    Retrieves the most recent saved conversations.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT timestamp, user_query, assistant_response FROM convo_history ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to retrieve recent history: {e}")
        return []
    finally:
        conn.close()

def get_local_reminders(limit: int = 5) -> list:
    """
    Retrieves upcoming/pending local reminders.
    Returns list of dicts.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, timestamp, title, scheduled_time, status FROM reminders ORDER BY scheduled_time ASC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to retrieve local reminders: {e}")
        return []
    finally:
        conn.close()

# Alias for API compatibility
save_interaction = log_interaction

# Initialize DB when module is imported
init_db()

