import urllib
import urllib.request
import urllib.error
import json
import logging

from typing import Tuple

logger = logging.getLogger("VoiceAssistant.LocalLLM")

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"

def query_local_llm(prompt: str) -> Tuple[bool, str]:
    """
    Queries the local Ollama LLM if running.
    Retrieves the list of installed models and uses the first available one (preferring llama/gemma).
    Returns (success, response_text).
    """
    logger.info(f"Offline AI query request: '{prompt}'")
    try:
        # 1. Fetch available models from local Ollama
        req_tags = urllib.request.Request(OLLAMA_TAGS_URL)
        try:
            with urllib.request.urlopen(req_tags, timeout=3) as response:
                tags_data = json.loads(response.read().decode())
        except Exception as err:
            logger.warning(f"Ollama is not running or accessible: {err}")
            return False, "Ollama is not running. Please start the Ollama application."
            
        models = [m["name"] for m in tags_data.get("models", [])]
        if not models:
            return False, "Ollama is running, but no models are installed. Please run 'ollama run llama3.2' or 'ollama run gemma2' to download a model."
            
        # 2. Select the best model (preferring llama or gemma)
        selected_model = models[0]
        for model in models:
            if "llama" in model.lower() or "gemma" in model.lower():
                selected_model = model
                break
                
        logger.info(f"Selected local model for query: '{selected_model}'")
        
        # 3. Query the selected model
        payload = {
            "model": selected_model,
            "prompt": f"Answer the following question clearly and concisely in one or two sentences: {prompt}",
            "stream": False
        }
        
        req = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=20) as response:
            res_data = json.loads(response.read().decode())
            ans = res_data.get("response", "").strip()
            
        if ans:
            # Strip out markdown symbols like * or ** to make speaking sound cleaner
            ans_clean = ans.replace("**", "").replace("*", "").replace("`", "")
            return True, f"[Offline AI - {selected_model}] {ans_clean}"
        else:
            return False, "The local model returned an empty response."
            
    except Exception as e:
        logger.error(f"Error querying local LLM: {e}")
        return False, f"Local AI error: {e}"
