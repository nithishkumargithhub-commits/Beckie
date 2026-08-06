import sys
import openwakeword
import openwakeword.utils
from openwakeword.model import Model
from faster_whisper import WhisperModel

print("=== Pre-downloading Jarvis Models ===")

try:
    print("Downloading openWakeWord models...")
    import openwakeword.utils
    openwakeword.utils.download_models()
    Model(wakeword_models=['hey_jarvis'], inference_framework="onnx")
    print("[OK] openWakeWord models cached.")
except Exception as e:
    print(f"[Error] Failed to download openWakeWord models: {e}")
    sys.exit(1)

try:
    print("Downloading Whisper base model...")
    WhisperModel("base", device="cpu", compute_type="int8")
    print("[OK] Whisper base model cached.")
except Exception as e:
    print(f"[Error] Failed to download Whisper: {e}")
    sys.exit(1)

print("=== All Jarvis Models Cached Successfully ===")
