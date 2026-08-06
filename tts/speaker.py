import sys
import asyncio
import os
import tempfile
import subprocess
import pyttsx3
import logging
import queue
import threading
import config

logger = logging.getLogger("VoiceAssistant.Speaker")

try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False

class Speaker:
    def __init__(self):
        self.speak_queue = queue.Queue()
        self.voice = getattr(config, "TTS_VOICE", "en-US-ChristopherNeural")
        self.current_mci_alias = None
        self.stop_requested = False
        self.worker_thread = threading.Thread(target=self._speak_worker, daemon=True)
        self.worker_thread.start()
        logger.info("Speaker background thread started.")

    def stop(self):
        """
        Instantly halts active speech output and clears pending speech queue (Barge-in).
        """
        self.stop_requested = True
        logger.info("Barge-in / Stop speech requested.")

        # 1. Stop active WinMM MCI audio playback if playing
        if sys.platform == "win32" and self.current_mci_alias:
            try:
                import ctypes
                ctypes.windll.winmm.mciSendStringW(f'stop {self.current_mci_alias}', None, 0, 0)
                ctypes.windll.winmm.mciSendStringW(f'close {self.current_mci_alias}', None, 0, 0)
            except Exception as e:
                logger.warning(f"Error stopping MCI playback: {e}")
            self.current_mci_alias = None

        # 2. Clear remaining items in queue
        while not self.speak_queue.empty():
            try:
                item = self.speak_queue.get_nowait()
                if item and len(item) > 1:
                    item[1].set()
                self.speak_queue.task_done()
            except Exception:
                break

        config.ASSISTANT_STATE = "idle"

    def _speak_edge_tts(self, text: str) -> bool:
        """
        Attempts to render speech using Microsoft Edge Neural TTS.
        Returns True on success, False on failure.
        """
        global HAS_EDGE_TTS
        try:
            import edge_tts
            HAS_EDGE_TTS = True
        except ImportError:
            HAS_EDGE_TTS = False
            return False
        
        tmp_mp3 = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
                tmp_mp3 = f.name

            communicate = edge_tts.Communicate(text, self.voice)
            
            # Robust asyncio execution for worker thread
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(communicate.save(tmp_mp3))
                loop.close()
            except Exception as loop_err:
                asyncio.run(communicate.save(tmp_mp3))

            if self.stop_requested:
                return True

            if os.path.exists(tmp_mp3) and os.path.getsize(tmp_mp3) > 0:
                # Fast native MP3 playback on Windows via winmm MCI (zero subprocess overhead)
                if sys.platform == "win32":
                    import ctypes
                    import time
                    alias = f"jarvis_tts_{int(time.time()*1000)}"
                    self.current_mci_alias = alias
                    ctypes.windll.winmm.mciSendStringW(f'open "{tmp_mp3}" type mpegvideo alias {alias}', None, 0, 0)
                    ctypes.windll.winmm.mciSendStringW(f'play {alias} wait', None, 0, 0)
                    ctypes.windll.winmm.mciSendStringW(f'close {alias}', None, 0, 0)
                    self.current_mci_alias = None
                    return True
                else:
                    ps_cmd = (
                        f"$wmp = New-Object -ComObject WMPlayer.OCX; "
                        f"$wmp.URL = '{tmp_mp3}'; "
                        f"$wmp.controls.play(); "
                        f"while ($wmp.playState -ne 1 -and $wmp.playState -ne 0) {{ Start-Sleep -Milliseconds 100 }}"
                    )
                    res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, timeout=30)
                    if res.returncode == 0:
                        return True
        except Exception as e:
            logger.warning(f"Edge-TTS playback failed or offline: {e}. Falling back to pyttsx3.")
        finally:
            if tmp_mp3 and os.path.exists(tmp_mp3):
                try:
                    os.remove(tmp_mp3)
                except Exception:
                    pass
        return False

    def _speak_worker(self):
        """
        Runs inside a dedicated background thread. Initializing pyttsx3 here
        binds the COM object to this specific thread, preventing RPC/threading crashes.
        """
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', config.TTS_RATE)
            engine.setProperty('volume', config.TTS_VOLUME)
            logger.info("pyttsx3 TTS engine initialized successfully inside worker thread.")
        except Exception as e:
            logger.error(f"Failed to initialize pyttsx3 engine in worker thread: {e}. Fallback audio will be disabled.")
            engine = None

        while True:
            item = self.speak_queue.get()
            if item is None:
                break
            text, done_event = item
            self.stop_requested = False
            
            # Save previous state and transition to speaking
            prev_state = config.ASSISTANT_STATE
            config.ASSISTANT_STATE = "speaking"
            
            try:
                # 1. Attempt Neural Edge-TTS
                success = self._speak_edge_tts(text)
                
                # 2. Fallback to pyttsx3
                if not success and engine and not self.stop_requested:
                    engine.say(text)
                    engine.runAndWait()
            except Exception as e:
                logger.error(f"Error speaking text in worker thread: {e}")
            finally:
                # Safely restore previous state
                config.ASSISTANT_STATE = prev_state
                self.speak_queue.task_done()
                done_event.set()

    def speak(self, text: str):
        """
        Prints the response to console and queues it to be spoken aloud.
        Blocks the calling thread until speech is complete or interrupted.
        """
        try:
            logger.info(f"[{config.ASSISTANT_NAME}]: {text}")
            print(f"\n[{config.ASSISTANT_NAME}]: {text}\n")
        except Exception:
            try:
                import sys
                safe_text = text.encode(sys.stdout.encoding or 'utf-8', errors='backslashreplace').decode(sys.stdout.encoding or 'utf-8')
                print(f"\n[{config.ASSISTANT_NAME}]: {safe_text}\n")
            except Exception:
                pass
        
        done_event = threading.Event()
        self.speak_queue.put((text, done_event))
        done_event.wait()

