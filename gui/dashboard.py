import os
import sys

# Ensure project root is in sys.path when executed directly
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

import queue
import logging
import threading
import datetime
import customtkinter as ctk
import pystray
from PIL import Image, ImageDraw
import config


try:
    import win32com.client
except ImportError:
    win32com = None

logger = logging.getLogger("VoiceAssistant.GUI")

class QueueLogHandler(logging.Handler):
    """
    Custom logging handler that puts log messages into a thread-safe Queue.
    """
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))

class FloatingHUD(ctk.CTkToplevel):
    def __init__(self, parent_app, command_runner_callback):
        super().__init__(parent_app)
        self.parent_app = parent_app
        self.command_runner = command_runner_callback

        self.title("Jarvis HUD")
        hud_w = 380
        hud_h = 520
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = max(10, screen_w - hud_w - 20)
        y = max(10, screen_h - hud_h - 60)
        self.geometry(f"{hud_w}x{hud_h}+{x}+{y}")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.configure(fg_color="#0F172A")

        # Header Frame
        self.header_frame = ctk.CTkFrame(self, fg_color="#1E293B", corner_radius=10)
        self.header_frame.pack(fill="x", padx=10, pady=(10, 5))

        self.title_lbl = ctk.CTkLabel(
            self.header_frame, 
            text="⚡ JARVIS HUD", 
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#00E5FF"
        )
        self.title_lbl.pack(side="left", padx=12, pady=8)

        self.close_btn = ctk.CTkButton(
            self.header_frame, 
            text="✕", 
            width=28, 
            height=28,
            fg_color="transparent", 
            hover_color="#EF4444", 
            command=self.hide_hud
        )
        self.close_btn.pack(side="right", padx=8, pady=4)

        # Status Bar
        self.status_lbl = ctk.CTkLabel(
            self, 
            text="● Listening for command...", 
            font=ctk.CTkFont(size=12, weight="bold"), 
            text_color="#10B981"
        )
        self.status_lbl.pack(anchor="w", padx=15, pady=(2, 5))

        # Chat scroll frame
        self.chat_scroll = ctk.CTkScrollableFrame(self, fg_color="#1E293B", corner_radius=10)
        self.chat_scroll.pack(fill="both", expand=True, padx=10, pady=5)

        # Input Frame
        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.pack(fill="x", padx=10, pady=10)
        self.input_frame.grid_columnconfigure(0, weight=1)

        self.cmd_entry = ctk.CTkEntry(
            self.input_frame, 
            placeholder_text="Type command here...",
            fg_color="#1E293B"
        )
        self.cmd_entry.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        self.cmd_entry.bind("<Return>", lambda e: self.send_command())

        self.send_btn = ctk.CTkButton(
            self.input_frame, 
            text="Send", 
            width=65, 
            fg_color="#0284C7", 
            hover_color="#0369A1",
            command=self.send_command
        )
        self.send_btn.grid(row=0, column=1)

        # Sync existing messages
        self.refresh_chat_bubbles()

    def hide_hud(self):
        self.withdraw()

    def refresh_chat_bubbles(self):
        for child in self.chat_scroll.winfo_children():
            child.destroy()
        for sender, text in self.parent_app.last_messages:
            self.add_hud_bubble(sender, text)

    def add_hud_bubble(self, sender: str, text: str):
        bubble_frame = ctk.CTkFrame(self.chat_scroll, fg_color="transparent")
        bubble_frame.pack(fill="x", padx=6, pady=4, anchor="w" if sender == "jarvis" else "e")

        bg_color = "#334155" if sender == "jarvis" else "#0284C7"
        lbl = ctk.CTkLabel(
            bubble_frame,
            text=text,
            wraplength=260,
            justify="left" if sender == "jarvis" else "right",
            fg_color=bg_color,
            corner_radius=10,
            padx=10,
            pady=6,
            font=ctk.CTkFont(size=12)
        )
        lbl.pack(anchor="w" if sender == "jarvis" else "e")
        try:
            self.chat_scroll._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def send_command(self):
        cmd_text = self.cmd_entry.get().strip()
        if not cmd_text:
            return
        self.cmd_entry.delete(0, "end")
        self.parent_app.add_chat_bubble("user", cmd_text)

        class MockStream:
            pass

        def run_hud_cmd():
            prev_state = getattr(config, "ASSISTANT_STATE", "idle")
            config.ASSISTANT_STATE = "processing"
            try:
                self.command_runner(cmd_text, MockStream())
            finally:
                config.ASSISTANT_STATE = prev_state

        threading.Thread(target=run_hud_cmd, daemon=True).start()

class DashboardApp(ctk.CTk):
    def __init__(self, log_queue, command_runner_callback):
        super().__init__()
        self.log_queue = log_queue
        self.command_runner = command_runner_callback
        self.tray_icon = None
        self.last_messages = []
        self.floating_hud = None

        # Visualizer animation state variables
        self.anim_angle = 0.0
        self.breath_val = 0.0
        self.breath_dir = 1
        self.smooth_volume = 0.0

        # Window configuration
        self.title(f"{config.ASSISTANT_NAME} Assistant Panel")
        self.geometry("950x600")
        self.resizable(True, True)
        
        # Windows styling
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Handle window close (X button) to minimize to tray instead of quitting
        self.protocol('WM_DELETE_WINDOW', self.minimize_to_tray)

        # ------------------ Layout Configuration ------------------
        self.grid_columnconfigure(0, weight=1)  # Sidebar
        self.grid_columnconfigure(1, weight=3)  # Main Content Panel
        self.grid_rowconfigure(0, weight=1)

        # ------------------ Sidebar Panel (Left) ------------------
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.sidebar_frame.grid_rowconfigure(5, weight=1)

        # Title
        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text=config.ASSISTANT_NAME.upper(), 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 5))
        
        self.version_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text=f"Version {config.VERSION}", 
            font=ctk.CTkFont(size=12, slant="italic"),
            text_color="gray"
        )
        self.version_label.grid(row=1, column=0, padx=20, pady=(0, 20))

        # Status Indicator
        self.status_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.status_frame.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        
        self.status_dot = ctk.CTkLabel(self.status_frame, text="●", text_color="#10B981", font=ctk.CTkFont(size=16)) # Green default
        self.status_dot.pack(side="left", padx=(5, 5))
        
        self.status_label = ctk.CTkLabel(self.status_frame, text="Status: Active", font=ctk.CTkFont(size=14, weight="bold"))
        self.status_label.pack(side="left")

        # Enable/Disable Voice Listening Switch
        self.listening_switch = ctk.CTkSwitch(
            self.sidebar_frame, 
            text="Voice Activation", 
            command=self.toggle_listening
        )
        self.listening_switch.grid(row=3, column=0, padx=20, pady=15, sticky="w")
        self.listening_switch.select() # Default to ON

        # Run at Startup Checkbox
        self.startup_checkbox = ctk.CTkCheckBox(
            self.sidebar_frame, 
            text="Run at Startup", 
            command=self.toggle_startup
        )
        self.startup_checkbox.grid(row=4, column=0, padx=20, pady=5, sticky="w")
        if self.check_startup_status():
            self.startup_checkbox.select()

        # Animated Visualizer Canvas Frame
        self.canvas_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.canvas_frame.grid(row=5, column=0, padx=20, pady=(10, 10), sticky="nsew")
        
        bg_color = self.sidebar_frame.cget("fg_color")
        if isinstance(bg_color, (list, tuple)):
            bg_color = bg_color[1] if len(bg_color) > 1 else bg_color[0]
            
        self.visualizer_canvas = ctk.CTkCanvas(
            self.canvas_frame, 
            width=160, 
            height=160, 
            bg=bg_color,
            highlightthickness=0
        )
        self.visualizer_canvas.pack(anchor="center", expand=True)

        # Hardware Monitor Card
        self.hardware_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="#1E293B", corner_radius=8)
        self.hardware_frame.grid(row=6, column=0, padx=20, pady=(10, 10), sticky="ew")
        
        self.cpu_lbl = ctk.CTkLabel(self.hardware_frame, text="CPU Usage: --%", font=ctk.CTkFont(size=12, weight="bold"))
        self.cpu_lbl.pack(pady=(8, 2), padx=10, anchor="w")
        self.cpu_progress = ctk.CTkProgressBar(self.hardware_frame, height=6, progress_color="#00E5FF")
        self.cpu_progress.pack(pady=4, padx=10, fill="x")
        self.cpu_progress.set(0.0)
        
        self.ram_lbl = ctk.CTkLabel(self.hardware_frame, text="RAM Usage: --%", font=ctk.CTkFont(size=12, weight="bold"))
        self.ram_lbl.pack(pady=(4, 2), padx=10, anchor="w")
        self.ram_progress = ctk.CTkProgressBar(self.hardware_frame, height=6, progress_color="#00E676")
        self.ram_progress.pack(pady=(4, 8), padx=10, fill="x")
        self.ram_progress.set(0.0)

        # Footer
        self.sidebar_footer = ctk.CTkLabel(
            self.sidebar_frame, 
            text="Minimize to System Tray\nto run in the background", 
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.sidebar_footer.grid(row=7, column=0, padx=20, pady=15, sticky="s")

        # ------------------ Main Tab Panel (Right) ------------------
        self.tabview = ctk.CTkTabview(self, corner_radius=10)
        self.tabview.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        # Tabs
        self.tabview.add("Conversation")
        self.tabview.add("Settings")
        self.tabview.add("Console Logs")

        # Configure tab grids
        self.tabview.tab("Conversation").grid_columnconfigure(0, weight=1)
        self.tabview.tab("Conversation").grid_rowconfigure(0, weight=1)
        self.tabview.tab("Conversation").grid_rowconfigure(1, weight=0)
        
        self.tabview.tab("Settings").grid_columnconfigure(0, weight=1)
        
        self.tabview.tab("Console Logs").grid_columnconfigure(0, weight=1)
        self.tabview.tab("Console Logs").grid_rowconfigure(0, weight=1)

        # ------------------ Tab 1: Conversation ------------------
        # Scrollable Chat bubble container
        self.chat_scroll = ctk.CTkScrollableFrame(self.tabview.tab("Conversation"), fg_color="transparent")
        self.chat_scroll.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")

        # Input box and Send button
        self.input_frame = ctk.CTkFrame(self.tabview.tab("Conversation"), fg_color="transparent")
        self.input_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        self.input_frame.grid_columnconfigure(0, weight=1)

        self.cmd_input = ctk.CTkEntry(
            self.input_frame, 
            placeholder_text="Type a command directly (e.g. 'open notepad', 'close spotify')..."
        )
        self.cmd_input.grid(row=0, column=0, padx=(0, 10), pady=0, sticky="ew")
        self.cmd_input.bind("<Return>", lambda event: self.send_text_command())

        self.send_btn = ctk.CTkButton(
            self.input_frame, 
            text="Send", 
            width=80, 
            fg_color="#0284C7", 
            hover_color="#0369A1",
            command=self.send_text_command
        )
        self.send_btn.grid(row=0, column=1, padx=0, pady=0)

        # ------------------ Tab 2: Settings ------------------
        # Scrollable Settings Container
        self.settings_frame = ctk.CTkScrollableFrame(self.tabview.tab("Settings"), fg_color="transparent")
        self.settings_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.settings_frame.grid_columnconfigure(0, weight=1)

        # API Key Section
        self.api_section_lbl = ctk.CTkLabel(self.settings_frame, text="Google Gemini Developer API Key", font=ctk.CTkFont(size=14, weight="bold"))
        self.api_section_lbl.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")

        self.api_entry_frame = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        self.api_entry_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        self.api_entry_frame.grid_columnconfigure(0, weight=1)

        self.api_key_val = os.getenv("GEMINI_API_KEY", "")
        self.api_key_entry = ctk.CTkEntry(self.api_entry_frame, show="*", placeholder_text="Enter API Key here...")
        self.api_key_entry.grid(row=0, column=0, padx=(0, 10), pady=0, sticky="ew")
        self.api_key_entry.insert(0, self.api_key_val)

        self.toggle_api_btn = ctk.CTkButton(self.api_entry_frame, text="Show", width=60, command=self.toggle_api_visibility)
        self.toggle_api_btn.grid(row=0, column=1, padx=0, pady=0)

        self.save_api_btn = ctk.CTkButton(self.settings_frame, text="Save API Key", width=120, command=self.save_api_key)
        self.save_api_btn.grid(row=2, column=0, padx=10, pady=(5, 20), sticky="w")

        # Wake Word Config
        self.ww_section_lbl = ctk.CTkLabel(self.settings_frame, text="Wake Word Configuration", font=ctk.CTkFont(size=14, weight="bold"))
        self.ww_section_lbl.grid(row=3, column=0, padx=10, pady=(10, 5), sticky="w")

        self.ww_select_lbl = ctk.CTkLabel(self.settings_frame, text="Select wake phrase:")
        self.ww_select_lbl.grid(row=4, column=0, padx=10, pady=2, sticky="w")

        current_ww = config.WAKE_WORDS[0] if config.WAKE_WORDS else "hey_jarvis"
        self.ww_dropdown = ctk.CTkComboBox(self.settings_frame, values=["hey_jarvis", "alexa", "hey_rhasspy", "weather"])
        self.ww_dropdown.grid(row=5, column=0, padx=10, pady=5, sticky="w")
        self.ww_dropdown.set(current_ww)

        # Sensitivity Slider
        self.sens_lbl_frame = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        self.sens_lbl_frame.grid(row=6, column=0, padx=10, pady=(15, 2), sticky="ew")
        
        self.sens_title = ctk.CTkLabel(self.sens_lbl_frame, text="Wake Word Sensitivity:")
        self.sens_title.pack(side="left")
        
        self.sens_val_lbl = ctk.CTkLabel(self.sens_lbl_frame, text=f"{config.WAKE_WORD_THRESHOLD:.2f}", font=ctk.CTkFont(weight="bold"))
        self.sens_val_lbl.pack(side="left", padx=10)

        self.sens_slider = ctk.CTkSlider(self.settings_frame, from_=0.1, to=1.0, number_of_steps=18, command=self.on_sens_slider)
        self.sens_slider.grid(row=7, column=0, padx=10, pady=5, sticky="ew")
        self.sens_slider.set(config.WAKE_WORD_THRESHOLD)

        self.tts_section_lbl = ctk.CTkLabel(self.settings_frame, text="Neural TTS Voice Selection", font=ctk.CTkFont(size=14, weight="bold"))
        self.tts_section_lbl.grid(row=8, column=0, padx=10, pady=(15, 5), sticky="w")

        self.tts_voice_dropdown = ctk.CTkComboBox(
            self.settings_frame,
            values=[
                "en-US-ChristopherNeural",
                "en-US-SteffanNeural",
                "en-US-AvaNeural",
                "en-US-GuyNeural",
                "en-GB-RyanNeural"
            ]
        )
        self.tts_voice_dropdown.grid(row=9, column=0, padx=10, pady=5, sticky="w")
        self.tts_voice_dropdown.set(getattr(config, "TTS_VOICE", "en-US-ChristopherNeural"))

        # Web, YouTube & Spotify Settings
        self.web_section_lbl = ctk.CTkLabel(self.settings_frame, text="Web, YouTube & Spotify Settings", font=ctk.CTkFont(size=14, weight="bold"))
        self.web_section_lbl.grid(row=10, column=0, padx=10, pady=(15, 5), sticky="w")

        self.web_songs_switch = ctk.CTkSwitch(
            self.settings_frame,
            text="Enable Web, YouTube & Spotify Song Playback"
        )
        self.web_songs_switch.grid(row=11, column=0, padx=10, pady=5, sticky="w")
        if getattr(config, "ENABLE_WEB_SONGS", True):
            self.web_songs_switch.select()
        else:
            self.web_songs_switch.deselect()

        self.email_entry_lbl = ctk.CTkLabel(self.settings_frame, text="Default Search Email (Chrome Profile):")
        self.email_entry_lbl.grid(row=12, column=0, padx=10, pady=(5, 2), sticky="w")

        default_email = getattr(config, "CHROME_DEFAULT_EMAIL", "nithishnithishkumar371@gmail.com")
        self.email_entry = ctk.CTkEntry(self.settings_frame, placeholder_text="Enter Gmail address...")
        self.email_entry.grid(row=13, column=0, padx=10, pady=5, sticky="ew")
        self.email_entry.insert(0, default_email)

        self.save_settings_btn = ctk.CTkButton(self.settings_frame, text="Save Settings", width=120, command=self.save_assistant_settings)
        self.save_settings_btn.grid(row=14, column=0, padx=10, pady=(20, 20), sticky="w")

        # ------------------ Tab 3: Console Logs ------------------
        self.console_box = ctk.CTkTextbox(self.tabview.tab("Console Logs"), wrap="word", font=ctk.CTkFont(family="Consolas", size=11))
        self.console_box.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.console_box.configure(state="disabled")

        # Add initial welcome chat bubble
        self.add_chat_bubble("jarvis", f"Welcome back! I am {config.ASSISTANT_NAME}. How can I assist you today?")

        # ------------------ System Tray Integration ------------------
        self.start_tray_icon()

        # Start Log Polling Loop
        self.after(100, self.poll_logs)
        
        # Start Visualizer Animation loop
        self.animate_orb()

        # Start Hardware Monitoring loop
        self.after(1000, self.poll_hardware)

    # ------------------ Logic Methods ------------------

    def poll_hardware(self):
        """
        Polls CPU and RAM status using psutil and updates sidebar metrics.
        """
        try:
            import psutil
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent
            
            self.cpu_lbl.configure(text=f"CPU Usage: {cpu:.1f}%")
            self.cpu_progress.set(cpu / 100.0)
            
            self.ram_lbl.configure(text=f"RAM Usage: {ram:.1f}%")
            self.ram_progress.set(ram / 100.0)
        except Exception as e:
            logger.warning(f"Error polling hardware metrics: {e}")
        self.after(1000, self.poll_hardware)

    def show_floating_hud(self):
        """
        Pops up or restores the floating overlay HUD on the right side of the screen.
        """
        def _show():
            if self.floating_hud is None or not self.floating_hud.winfo_exists():
                self.floating_hud = FloatingHUD(self, self.command_runner)
            else:
                self.floating_hud.deiconify()
                self.floating_hud.lift()
                self.floating_hud.attributes("-topmost", True)
                self.floating_hud.focus_force()
                self.floating_hud.refresh_chat_bubbles()
        self.after(0, _show)

    def add_chat_bubble(self, sender: str, text: str):
        """
        Appends a styled speech bubble to the conversation tab and floating HUD.
        De-duplicates identical consecutive messages.
        """
        if self.last_messages and self.last_messages[-1] == (sender, text):
            return
        self.last_messages.append((sender, text))
        if len(self.last_messages) > 50:
            self.last_messages.pop(0)

        def main_thread_add():
            bubble_frame = ctk.CTkFrame(self.chat_scroll, fg_color="transparent")
            bubble_frame.pack(fill="x", padx=10, pady=6, anchor="w" if sender == "jarvis" else "e")
            
            # Align and style
            bg_color = "#1F2937" if sender == "jarvis" else "#0284C7"
            align = "w" if sender == "jarvis" else "e"
            pad = (0, 60) if sender == "jarvis" else (60, 0)
            
            card = ctk.CTkFrame(bubble_frame, fg_color=bg_color, corner_radius=12)
            card.pack(anchor=align, padx=pad)
            
            sender_title = f"🤖 {config.ASSISTANT_NAME}" if sender == "jarvis" else "👤 You"
            title_lbl = ctk.CTkLabel(card, text=sender_title, font=ctk.CTkFont(size=10, weight="bold"), text_color="#9CA3AF" if sender == "jarvis" else "#E0F2FE")
            title_lbl.pack(anchor="w", padx=12, pady=(6, 2))
            
            msg_lbl = ctk.CTkLabel(card, text=text, font=ctk.CTkFont(size=13), text_color="#F3F4F6" if sender == "jarvis" else "#FFFFFF", justify="left", wraplength=450)
            msg_lbl.pack(anchor="w", padx=12, pady=(2, 8))
            
            # Autoscroll
            try:
                self.chat_scroll._parent_canvas.yview_moveto(1.0)
            except Exception:
                pass

            if self.floating_hud and self.floating_hud.winfo_exists():
                self.floating_hud.add_hud_bubble(sender, text)
            
        self.after(0, main_thread_add)

    def poll_logs(self):
        """
        Polls the log queue and appends any pending logs to the console textbox.
        Also parses standard output messages for dialogue bubbles.
        """
        try:
            while True:
                message = self.log_queue.get_nowait()
                
                # Insert to raw activity log textbox
                self.console_box.configure(state="normal")
                self.console_box.insert("end", message + "\n")
                self.console_box.see("end")
                self.console_box.configure(state="disabled")
                
                # Dialogue Parsing
                if f"[{config.ASSISTANT_NAME}]:" in message:
                    parts = message.split(f"[{config.ASSISTANT_NAME}]:", 1)
                    text = parts[1].strip()
                    if text:
                        self.add_chat_bubble("jarvis", text)
                elif "[User]:" in message:
                    parts = message.split("[User]:", 1)
                    text = parts[1].strip()
                    if text:
                        self.add_chat_bubble("user", text)
                elif "VoiceAssistant.Transcriber: Result:" in message:
                    parts = message.split("Result:", 1)
                    text = parts[1].strip()
                    if text:
                        self.add_chat_bubble("user", text)
                        
                self.log_queue.task_done()
        except queue.Empty:
            pass
        self.after(100, self.poll_logs)

    def animate_orb(self):
        """
        Calculates and draws the animated AI status orb on the canvas based on config.ASSISTANT_STATE.
        """
        # Schedule the next frame
        self.after(30, self.animate_orb)
        
        # Clear canvas
        self.visualizer_canvas.delete("all")
        
        # Pull live values
        state = getattr(config, "ASSISTANT_STATE", "idle")
        vol = getattr(config, "CURRENT_VOLUME", 0.0)
        
        self.smooth_volume = self.smooth_volume * 0.6 + vol * 0.4
        cx, cy = 80, 80 # center
        
        import math
        import random
        
        if state == "listening":
            r_base = 35 + 25 * self.smooth_volume
            self.visualizer_canvas.create_oval(cx - r_base - 10, cy - r_base - 10, cx + r_base + 10, cy + r_base + 10, fill="#1E293B", outline="#00E5FF", width=1)
            self.visualizer_canvas.create_oval(cx - r_base, cy - r_base, cx + r_base, cy + r_base, fill="#00E5FF", outline="#E0F7FC", width=2)
            self.visualizer_canvas.create_oval(cx - r_base/1.5, cy - r_base/1.5, cx - r_base/4, cy - r_base/4, fill="#E0F7FC", outline="")
            
            for i, x in enumerate([25, 45, 65, 85, 105, 125, 145]):
                mult = 1.0 - abs(i - 3) * 0.25
                height = 4 + 45 * self.smooth_volume * mult * random.uniform(0.7, 1.3)
                self.visualizer_canvas.create_rectangle(x - 2, cy - height, x + 2, cy + height, fill="#E0F7FC", outline="")
                
        elif state == "processing":
            self.anim_angle += 0.08
            r_base = 38
            self.visualizer_canvas.create_oval(cx - 52, cy - 52, cx + 52, cy + 52, outline="#334155", width=1)
            self.visualizer_canvas.create_oval(cx - r_base, cy - r_base, cx + r_base, cy + r_base, fill="#FF8F00", outline="#FFB300", width=2)
            self.visualizer_canvas.create_oval(cx - r_base/1.5, cy - r_base/1.5, cx - r_base/4, cy - r_base/4, fill="#FFE082", outline="")
            
            for j in range(4):
                angle = self.anim_angle + j * (math.pi / 2)
                px = cx + 52 * math.cos(angle)
                py = cy + 52 * math.sin(angle)
                self.visualizer_canvas.create_oval(px - 5, py - 5, px + 5, py + 5, fill="#FFD54F", outline="#FF8F00", width=1)
                
        elif state == "speaking":
            self.breath_val += 0.06 * self.breath_dir
            if self.breath_val > 1.0:
                self.breath_val = 1.0
                self.breath_dir = -1
            elif self.breath_val < 0.0:
                self.breath_val = 0.0
                self.breath_dir = 1
                
            r_base = 35 + 10 * self.breath_val
            
            for r_offset in [15, 30]:
                ripple_r = r_base + r_offset * self.breath_val
                alpha_color = "#34D399" if r_offset == 15 else "#6EE7B7"
                self.visualizer_canvas.create_oval(cx - ripple_r, cy - ripple_r, cx + ripple_r, cy + ripple_r, outline=alpha_color, width=1)
                
            self.visualizer_canvas.create_oval(cx - r_base, cy - r_base, cx + r_base, cy + r_base, fill="#00E676", outline="#B9F6CA", width=2)
            self.visualizer_canvas.create_oval(cx - r_base/1.5, cy - r_base/1.5, cx - r_base/4, cy - r_base/4, fill="#E8F5E9", outline="")
            
        else:
            self.breath_val += 0.02 * self.breath_dir
            if self.breath_val > 1.0:
                self.breath_val = 1.0
                self.breath_dir = -1
            elif self.breath_val < 0.0:
                self.breath_val = 0.0
                self.breath_dir = 1
                
            r_base = 35 + 8 * self.breath_val
            self.visualizer_canvas.create_oval(cx - r_base - 15, cy - r_base - 15, cx + r_base + 15, cy + r_base + 15, fill="#0F172A", outline="#1E293B", width=1)
            self.visualizer_canvas.create_oval(cx - r_base - 8, cy - r_base - 8, cx + r_base + 8, cy + r_base + 8, fill="#1E293B", outline="#00B4D8", width=1)
            self.visualizer_canvas.create_oval(cx - r_base, cy - r_base, cx + r_base, cy + r_base, fill="#00B4D8", outline="#00E5FF", width=2)
            self.visualizer_canvas.create_oval(cx - r_base/1.5, cy - r_base/1.5, cx - r_base/4, cy - r_base/4, fill="#E0F7FC", outline="")

    def send_text_command(self):
        """
        Submits the text command from input box to be processed.
        Executed in a separate worker thread to prevent GUI lockups.
        """
        cmd_text = self.cmd_input.get().strip()
        if not cmd_text:
            return
        
        self.cmd_input.delete(0, "end")
        
        # Log User command directly so it shows up in conversation view and logs
        logger.info(f"[User]: {cmd_text}")

        # Run command runner callback in thread with visualizer state wrapping
        class MockStream:
            def read(self, *args, **kwargs):
                return b""
        
        def run_gui_cmd():
            prev_state = getattr(config, "ASSISTANT_STATE", "idle")
            config.ASSISTANT_STATE = "processing"
            try:
                self.command_runner(cmd_text, MockStream())
            finally:
                config.ASSISTANT_STATE = prev_state

        threading.Thread(
            target=run_gui_cmd, 
            daemon=True
        ).start()

    def toggle_listening(self):
        """
        Toggles voice assistant listening state.
        """
        config.ASSISTANT_ENABLED = self.listening_switch.get() == 1
        if config.ASSISTANT_ENABLED:
            self.status_dot.configure(text_color="#10B981")
            self.status_label.configure(text="Status: Active")
            logger.info("Voice Assistant listening ENABLED.")
        else:
            self.status_dot.configure(text_color="#F59E0B")
            self.status_label.configure(text="Status: Paused")
            logger.info("Voice Assistant listening PAUSED.")

    def on_sens_slider(self, val):
        self.sens_val_lbl.configure(text=f"{val:.2f}")

    def toggle_api_visibility(self):
        if self.api_key_entry.cget("show") == "*":
            self.api_key_entry.configure(show="")
            self.toggle_api_btn.configure(text="Hide")
        else:
            self.api_key_entry.configure(show="*")
            self.toggle_api_btn.configure(text="Show")

    def save_api_key(self):
        new_key = self.api_key_entry.get().strip()
        config.save_env_var("GEMINI_API_KEY", new_key)
        logger.info("Gemini API Key successfully saved and updated.")

    def save_assistant_settings(self):
        ww = self.ww_dropdown.get()
        sens = self.sens_slider.get()
        tts_voice = self.tts_voice_dropdown.get()
        enable_web = self.web_songs_switch.get() == 1
        email = self.email_entry.get().strip()
        
        # Save variables to env file
        config.save_env_var("WAKE_WORD", ww)
        config.save_env_var("WAKE_WORD_THRESHOLD", f"{sens:.2f}")
        config.save_env_var("TTS_VOICE", tts_voice)
        config.save_env_var("ENABLE_WEB_SONGS", str(enable_web))
        config.save_env_var("CHROME_DEFAULT_EMAIL", email)
        
        # Update running values
        config.WAKE_WORDS = [ww]
        config.WAKE_WORD_THRESHOLD = sens
        config.TTS_VOICE = tts_voice
        config.ENABLE_WEB_SONGS = enable_web
        config.CHROME_DEFAULT_EMAIL = email
        
        logger.info(f"Settings saved. Active Wake Word: '{ww}' (Sensitivity: {sens:.2f}), Voice: '{tts_voice}', Web Songs: {enable_web}, Chrome Email: '{email}'")

    # ------------------ Startup & Tray Management ------------------

    def check_startup_status(self) -> bool:
        startup_folder = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup")
        shortcut_path = os.path.join(startup_folder, "JarvisVoiceAssistant.lnk")
        return os.path.exists(shortcut_path)

    def toggle_startup(self):
        enabled = self.startup_checkbox.get() == 1
        startup_folder = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup")
        shortcut_path = os.path.join(startup_folder, "JarvisVoiceAssistant.lnk")
        
        try:
            if enabled:
                import win32com.client
                shell = win32com.client.Dispatch("WScript.Shell")
                shortcut = shell.CreateShortCut(shortcut_path)
                shortcut.Targetpath = os.path.join(config.BASE_DIR, "jarvis.bat")
                shortcut.WorkingDirectory = config.BASE_DIR
                shortcut.save()
                logger.info("Startup shortcut successfully created.")
            else:
                if os.path.exists(shortcut_path):
                    os.remove(shortcut_path)
                    logger.info("Startup shortcut successfully removed.")
        except Exception as e:
            logger.error(f"Failed to configure startup shortcut: {e}")

    def minimize_to_tray(self):
        """
        Hides the GUI window, leaving the system tray icon running.
        """
        self.withdraw()
        logger.info("GUI minimized to system tray.")

    def restore_from_tray(self):
        """
        Restores and focuses the GUI window.
        """
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.attributes("-topmost", False)
        self.focus_force()
        logger.info("GUI restored from system tray.")

    def start_tray_icon(self):
        """
        Initializes and runs the PyStray system tray icon in a background thread.
        """
        # Generate dynamic microphone icon
        image = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
        dc = ImageDraw.Draw(image)
        dc.ellipse([16, 8, 48, 40], fill=(0, 150, 255, 255))
        dc.rectangle([28, 40, 36, 56], fill=(0, 150, 255, 255))
        dc.rectangle([20, 52, 44, 58], fill=(0, 150, 255, 255))

        def on_restore(icon, item):
            self.after(0, self.restore_from_tray)

        def on_exit(icon, item):
            icon.stop()
            self.after(0, self.quit_app)

        menu = pystray.Menu(
            pystray.MenuItem('Show Dashboard', on_restore, default=True),
            pystray.MenuItem('Exit', on_exit)
        )

        self.tray_icon = pystray.Icon("JarvisIcon", image, "Jarvis Voice Assistant", menu)
        
        # Start running pystray in a daemon background thread
        threading.Thread(target=self.tray_icon.run, daemon=True).start()
        logger.info("System Tray icon started.")

    def quit_app(self):
        """
        Handles clean exit of the entire voice assistant program.
        """
        logger.info("Exiting application...")
        if self.tray_icon:
            self.tray_icon.stop()
        self.destroy()
        sys.exit(0)
