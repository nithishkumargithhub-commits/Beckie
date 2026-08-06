import os
import logging
from typing import Tuple
from google import genai
import config

logger = logging.getLogger("VoiceAssistant.Clipboard")

try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False

def get_clipboard_text() -> str:
    """
    Retrieves current text contents from system clipboard.
    """
    if HAS_PYPERCLIP:
        try:
            return pyperclip.paste() or ""
        except Exception:
            pass
    try:
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        text = r.clipboard_get()
        r.destroy()
        return text or ""
    except Exception:
        return ""

def set_clipboard_text(text: str) -> bool:
    """
    Copies text onto system clipboard.
    """
    if HAS_PYPERCLIP:
        try:
            pyperclip.copy(text)
            return True
        except Exception:
            pass
    try:
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        r.clipboard_clear()
        r.clipboard_append(text)
        r.update()
        r.destroy()
        return True
    except Exception:
        return False

def process_clipboard_action(action: str) -> Tuple[bool, str]:
    """
    Performs AI smart actions on copied clipboard text.
    action can be: 'explain', 'summarize', 'fix', 'read'
    """
    clipboard_content = get_clipboard_text().strip()
    if not clipboard_content:
        return False, "Your clipboard is currently empty. Please copy some text first."

    act = action.lower().strip()
    logger.info(f"Clipboard processing request: '{act}' (content length: {len(clipboard_content)} chars)")

    if act in ["read", "get", "paste", "show"]:
        preview = clipboard_content[:150] + ("..." if len(clipboard_content) > 150 else "")
        return True, f"Clipboard content: {preview}"

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return False, "Gemini API key is required to analyze clipboard text."

    client = genai.Client(api_key=api_key)

    if "explain" in act:
        prompt = f"Explain the following copied text or code clearly and concisely in 2 to 3 sentences:\n\n{clipboard_content[:2000]}"
    elif "fix" in act or "correct" in act or "proofread" in act:
        prompt = f"Fix any grammar, spelling, or code errors in the following text and return ONLY the corrected text:\n\n{clipboard_content[:2000]}"
    else:  # Summarize
        prompt = f"Summarize the following text clearly in 2 short sentences:\n\n{clipboard_content[:2000]}"

    try:
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt
        )
        res_text = response.text.strip() if response and response.text else ""
        if res_text:
            clean_res = res_text.replace("**", "").replace("*", "").replace("`", "")
            if "fix" in act or "correct" in act:
                set_clipboard_text(clean_res)
                return True, f"I have corrected your copied text and updated your clipboard. Here is the corrected text: {clean_res}"
            return True, clean_res
        else:
            return False, "AI returned an empty analysis for your clipboard text."
    except Exception as e:
        logger.error(f"Error processing clipboard text: {e}")
        return False, f"Failed to process clipboard text: {e}"
