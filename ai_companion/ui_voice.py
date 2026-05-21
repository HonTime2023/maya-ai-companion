"""
Voice-Only UI: JARVIS-style interface for AI Companion
Shows listening state, real-time transcription, and AI responses
No text input - voice only
"""

import tkinter as tk
from tkinter import font as tkFont
import threading
import queue
import time
from datetime import datetime

# Setup logging
try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger("VoiceUI")
    logger.basicConfig(level=logging.INFO)


class AICompanionVoiceUI:
    """JARVIS-style voice interface for AI Companion"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("AI Companion - Voice Mode")
        self.root.geometry("800x600")
        self.root.configure(bg="#0a0e27")
        
        # State machine
        self.state = "idle"  # idle, listening, transcribing, thinking, speaking
        self.current_transcript = ""
        self.current_response = ""
        self.message_queue = queue.Queue()
        
        self._setup_ui()
        self._start_message_processor()
        
        logger.info("Voice UI initialized")
    
    def _setup_ui(self):
        """Setup the voice-only interface"""
        
        # Title
        title_font = tkFont.Font(family="Arial", size=24, weight="bold")
        title = tk.Label(
            self.root,
            text="AI COMPANION - VOICE MODE",
            font=title_font,
            fg="#00d4ff",
            bg="#0a0e27"
        )
        title.pack(pady=20)
        
        # Status indicator (color changes based on state)
        self.status_var = tk.StringVar(value="● Idle")
        status_font = tkFont.Font(family="Arial", size=14, weight="bold")
        self.status_label = tk.Label(
            self.root,
            textvariable=self.status_var,
            font=status_font,
            fg="#00ff00",
            bg="#0a0e27"
        )
        self.status_label.pack(pady=10)
        
        # Waveform simulation (visual feedback)
        self.waveform_canvas = tk.Canvas(
            self.root,
            width=700,
            height=80,
            bg="#0a0e27",
            highlightthickness=0
        )
        self.waveform_canvas.pack(pady=15)
        self.waveform_bars = []
        self._create_waveform_bars()
        
        # Transcription display
        transcript_label = tk.Label(
            self.root,
            text="Transcription:",
            font=("Arial", 12),
            fg="#aaaaaa",
            bg="#0a0e27"
        )
        transcript_label.pack(anchor="w", padx=50, pady=(20, 5))
        
        self.transcript_var = tk.StringVar(value="[Waiting for speech...]")
        transcript_display = tk.Label(
            self.root,
            textvariable=self.transcript_var,
            font=("Arial", 11),
            fg="#00d4ff",
            bg="#1a1f3a",
            wraplength=700,
            justify="left",
            padx=10,
            pady=10
        )
        transcript_display.pack(padx=50, pady=(0, 10), fill="x")
        
        # AI Response display
        response_label = tk.Label(
            self.root,
            text="AI Response:",
            font=("Arial", 12),
            fg="#aaaaaa",
            bg="#0a0e27"
        )
        response_label.pack(anchor="w", padx=50, pady=(15, 5))
        
        self.response_var = tk.StringVar(value="[Waiting for response...]")
        response_display = tk.Label(
            self.root,
            textvariable=self.response_var,
            font=("Arial", 10),
            fg="#00ff88",
            bg="#1a1f3a",
            wraplength=650,
            justify="left",
            padx=10,
            pady=10
        )
        response_display.pack(padx=50, pady=(0, 20), fill="x")
        
        # Status bar
        status_bar = tk.Frame(self.root, bg="#00d4ff", height=2)
        status_bar.pack(side="bottom", fill="x")
        
        info_text = "Voice-activated AI • Press Ctrl+C to exit"
        info_label = tk.Label(
            self.root,
            text=info_text,
            font=("Arial", 9),
            fg="#999999",
            bg="#0a0e27"
        )
        info_label.pack(side="bottom", pady=10)
    
    def _create_waveform_bars(self):
        """Create animated waveform bars"""
        bar_width = 8
        bar_spacing = 2
        total_width = 700
        num_bars = total_width // (bar_width + bar_spacing)
        
        for i in range(num_bars):
            x = i * (bar_width + bar_spacing) + 50
            bar = self.waveform_canvas.create_rectangle(
                x, 40, x + bar_width, 40,
                fill="#00d4ff", outline="#00d4ff"
            )
            self.waveform_bars.append(bar)
    
    def set_state(self, new_state):
        """Update UI state and colors"""
        self.state = new_state
        
        state_colors = {
            "idle": ("#888888", "● Idle"),
            "listening": ("#00d4ff", "● LISTENING..."),
            "transcribing": ("#00ff88", "● Transcribing..."),
            "thinking": ("#ffaa00", "● AI Thinking..."),
            "speaking": ("#ff6600", "● Speaking Response..."),
        }
        
        if new_state in state_colors:
            color, text = state_colors[new_state]
            self.status_var.set(text)
            self.status_label.config(fg=color)
            logger.info(f"State changed to: {new_state}")
    
    def update_transcript(self, text):
        """Update transcription display"""
        self.current_transcript = text
        if text:
            self.transcript_var.set(f"You said: \"{text}\"")
        else:
            self.transcript_var.set("[No speech detected]")
        self.root.update()
    
    def stream_ai_response(self, response_generator):
        """Stream AI response chunks to UI"""
        self.set_state("thinking")
        self.response_var.set("")
        
        full_response = ""
        for chunk in response_generator:
            full_response += chunk
            self.response_var.set(full_response)
            self.root.update()
            time.sleep(0.01)  # Small delay for smooth display
        
        self.set_state("speaking")
        logger.info(f"Full response: {full_response}")
        return full_response
    
    def animate_waveform(self):
        """Animate waveform bars based on state"""
        import random
        
        def animate():
            if self.state == "listening":
                heights = [random.randint(10, 35) for _ in self.waveform_bars]
                for i, bar in enumerate(self.waveform_bars):
                    h = heights[i]
                    self.waveform_canvas.coords(
                        bar,
                        i * 10 + 50,
                        40 - h,
                        i * 10 + 58,
                        40 + h
                    )
                self.root.after(50, animate)
            elif self.state == "idle":
                # Idle - all bars at minimum
                for i, bar in enumerate(self.waveform_bars):
                    self.waveform_canvas.coords(
                        bar,
                        i * 10 + 50,
                        35,
                        i * 10 + 58,
                        45
                    )
        
        animate()
    
    def _start_message_processor(self):
        """Start processor for queue messages"""
        def processor():
            while True:
                try:
                    msg_type, data = self.message_queue.get(timeout=0.1)
                    
                    if msg_type == "state":
                        self.set_state(data)
                    elif msg_type == "transcript":
                        self.update_transcript(data)
                    elif msg_type == "response":
                        self.stream_ai_response(data)
                    elif msg_type == "waveform":
                        self.animate_waveform()
                        
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"Message processor error: {e}")
        
        thread = threading.Thread(target=processor, daemon=True)
        thread.start()
    
    def send_message(self, msg_type, data):
        """Thread-safe message sending to UI"""
        self.message_queue.put((msg_type, data))
    
    def show_listening(self):
        """Show listening state"""
        self.send_message("state", "listening")
        self.send_message("waveform", None)
    
    def show_transcription(self, text):
        """Show transcription result"""
        self.send_message("state", "transcribing")
        self.send_message("transcript", text)
    
    def show_response(self, response_gen):
        """Show AI response"""
        self.send_message("response", response_gen)
    
    def show_idle(self):
        """Show idle state"""
        self.send_message("state", "idle")
        self.response_var.set("[Waiting for response...]")


def launch_ui():
    """Launch the voice UI (called by run_full.py) - returns UI object"""
    root = tk.Tk()
    ui = AICompanionVoiceUI(root)
    
    # Start animation loop
    ui.animate_waveform()
    
    return ui, root


def main():
    """Launch the voice UI for testing"""
    root = tk.Tk()
    ui = AICompanionVoiceUI(root)
    
    # Test sequence to show UI working
    ui.show_listening()
    root.after(2000, lambda: ui.show_transcription("What time is it"))
    root.after(4000, lambda: ui.show_idle())
    
    root.mainloop()


if __name__ == "__main__":
    main()
