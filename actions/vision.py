import os
import tempfile
import logging
from typing import Tuple
from PIL import ImageGrab, Image
from google import genai
import config

logger = logging.getLogger("VoiceAssistant.Vision")

def analyze_screen_with_ai(prompt_text: str = "") -> Tuple[bool, str]:
    """
    Captures a screenshot of the user screen and uses Gemini Vision
    to describe, analyze, summarize, or debug what is on the monitor.
    """
    logger.info(f"Screen vision request with prompt: '{prompt_text}'")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return False, "Gemini API key is not configured. Screen vision requires a valid Gemini API key."

    tmp_path = None
    try:
        # 1. Capture screen
        screenshot = ImageGrab.grab()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f:
            tmp_path = f.name
        screenshot.save(tmp_path, format="PNG")
        logger.info(f"Screenshot saved temporarily to: {tmp_path}")

        # 2. Open image for Gemini
        img = Image.open(tmp_path)

        # 3. Build prompt
        query_prompt = prompt_text.strip() if prompt_text.strip() else "Analyze what is visible on the screen and summarize the main content, open application, or any visible text/errors concisely in 2 to 3 sentences."
        sys_instructions = (
            "You are Jarvis, a helpful desktop voice assistant. Analyze the provided screenshot of the user computer monitor "
            "and answer their query clearly, concisely, and directly in 2 to 3 spoken sentences without markdown formatting."
        )

        from google.genai import types
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=[query_prompt, img],
            config=types.GenerateContentConfig(system_instruction=sys_instructions)
        )
        img.close()

        analysis = response.text.strip() if response and response.text else ""
        if analysis:
            analysis_clean = analysis.replace("**", "").replace("*", "").replace("`", "")
            logger.info("Screen vision analysis completed successfully.")
            return True, analysis_clean
        else:
            return False, "Screen vision model returned an empty response."

    except Exception as e:
        logger.error(f"Error during screen vision analysis: {e}")
        return False, f"Failed to analyze screen: {e}"
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
