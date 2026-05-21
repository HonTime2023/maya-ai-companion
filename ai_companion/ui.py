"""
UI: Tkinter-based GUI for AI Companion.
Provides text-based interaction for end-to-end testing without heavy pygame dependency.
"""

import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog
import threading
import os
from dotenv import load_dotenv

load_dotenv()

from brain import think_stream
from conversation import add_user_message, add_ai_message
from user_manager import get_current_user, get_current_user_name
from intent_router import detect_intent
from intent_handlers import handle_intent
from reminders import add_reminder, check_reminders, list_reminders
from alarms import add_alarm, check_alarms, list_alarms


class AICompanionUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Companion - Text Interface")
        self.root.geometry("900x700")
        self.root.config(bg="#f0f0f0")

        self.user = get_current_user()
        self.processing = False

        self._setup_ui()
        self._onboard_if_needed()
        self._check_reminders_loop()

    def _setup_ui(self):
        """Setup UI components."""
        # Header
        header = tk.Frame(self.root, bg="#2c3e50", height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        user_name = self.user.get_name() or "User"
        title = tk.Label(
            header,
            text=f"🤖 AI Companion - {user_name}",
            font=("Arial", 16, "bold"),
            fg="white",
            bg="#2c3e50",
        )
        title.pack(pady=10)

        # Conversation display
        conv_frame = tk.Frame(self.root, bg="white")
        conv_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.conversation_display = scrolledtext.ScrolledText(
            conv_frame,
            wrap=tk.WORD,
            font=("Courier", 10),
            height=20,
            state=tk.DISABLED,
            bg="white",
            fg="#333",
        )
        self.conversation_display.pack(fill=tk.BOTH, expand=True)

        # Configure tags
        self.conversation_display.tag_config("user", foreground="#0066cc", font=("Courier", 10, "bold"))
        self.conversation_display.tag_config("ai", foreground="#009900", font=("Courier", 10))
        self.conversation_display.tag_config("system", foreground="#666666", font=("Courier", 9, "italic"))

        # Input frame
        input_frame = tk.Frame(self.root, bg="#f0f0f0")
        input_frame.pack(fill=tk.X, padx=10, pady=10)

        self.input_field = tk.Entry(
            input_frame, font=("Arial", 11), width=70, bg="white", fg="#333"
        )
        self.input_field.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.input_field.bind("<Return>", lambda e: self._send_message())

        self.send_btn = tk.Button(
            input_frame,
            text="Send",
            font=("Arial", 10, "bold"),
            bg="#0066cc",
            fg="white",
            command=self._send_message,
        )
        self.send_btn.pack(side=tk.LEFT, padx=2)

        # Quick action buttons
        button_frame = tk.Frame(self.root, bg="#f0f0f0")
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Button(
            button_frame,
            text="📋 My Reminders",
            bg="#ff9800",
            fg="white",
            command=self._show_reminders,
            font=("Arial", 9),
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            button_frame,
            text="⏰ My Alarms",
            bg="#f44336",
            fg="white",
            command=self._show_alarms,
            font=("Arial", 9),
        ).pack(side=tk.LEFT, padx=2)

        # Status bar
        self.status_var = tk.StringVar(value="✅ Ready")
        status_bar = tk.Label(
            self.root,
            textvariable=self.status_var,
            font=("Arial", 9),
            bg="#e0e0e0",
            fg="#333",
            relief=tk.SUNKEN,
        )
        status_bar.pack(fill=tk.X)

        self._display_system_message("AI Companion initialized. Ready to help!")

    def _onboard_if_needed(self):
        """Check if user needs onboarding."""
        if not self.user.data.get("onboarded"):
            name = simpledialog.askstring("Welcome", "What's your name?")
            if name and len(name) > 2:
                self.user.update_name(name)
                self._display_ai_message(f"Nice to meet you, {name}!")

                wake_pref = messagebox.askyesno(
                    "Preferences",
                    "Use wake words (Yes) or natural mode (No)?",
                )
                if wake_pref:
                    self.user.update_preferences(
                        {"use_wake_words": True, "natural_mode": False}
                    )
                    self._display_ai_message("I'll listen for 'Jarvis'.")
                else:
                    self.user.update_preferences(
                        {"use_wake_words": False, "natural_mode": True}
                    )
                    self._display_ai_message("Natural conversation mode enabled.")

                self.user.data["onboarded"] = True
                self.user.save_profile()

    def _send_message(self):
        """Send user message and get AI response."""
        user_input = self.input_field.get().strip()
        if not user_input:
            return

        if self.processing:
            messagebox.showwarning("Busy", "Please wait...")
            return

        self.input_field.delete(0, tk.END)
        self._display_user_message(user_input)

        threading.Thread(target=self._process_message, args=(user_input,), daemon=True).start()

    def _process_message(self, user_text):
        """Process user message and generate response."""
        self.processing = True
        self.status_var.set("⏳ Processing...")

        try:
            add_user_message(user_text)
            intent = detect_intent(user_text.lower())

            if intent:
                try:
                    response = handle_intent(intent, user_text)
                    if response:
                        add_ai_message(response)
                        self._display_ai_message(response)
                except Exception as e:
                    msg = f"Error: {str(e)}"
                    self._display_system_message(msg)
            else:
                self._stream_ai_response()

            self.status_var.set("✅ Ready")
        except Exception as e:
            self._display_system_message(f"❌ Error: {str(e)}")
            self.status_var.set("❌ Error")
        finally:
            self.processing = False

    def _stream_ai_response(self):
        """Stream AI response."""
        full_response = ""
        try:
            for chunk in think_stream():
                full_response += chunk
                self._display_ai_stream(full_response)
                self.root.update()

            add_ai_message(full_response)
        except Exception as e:
            self._display_system_message(f"❌ Error: {str(e)}")

    def _display_user_message(self, text):
        """Display user message."""
        self.conversation_display.config(state=tk.NORMAL)
        self.conversation_display.insert(tk.END, f"\n👤 You: ", "user")
        self.conversation_display.insert(tk.END, text + "\n", "")
        self.conversation_display.see(tk.END)
        self.conversation_display.config(state=tk.DISABLED)

    def _display_ai_message(self, text):
        """Display AI message."""
        self.conversation_display.config(state=tk.NORMAL)
        self.conversation_display.insert(tk.END, f"\n🤖 AI: ", "ai")
        self.conversation_display.insert(tk.END, text + "\n", "")
        self.conversation_display.see(tk.END)
        self.conversation_display.config(state=tk.DISABLED)

    def _display_ai_stream(self, text):
        """Display streaming response."""
        self.conversation_display.config(state=tk.NORMAL)
        content = self.conversation_display.get("1.0", tk.END)
        if "🤖 AI:" in content:
            last_ai = content.rfind("🤖 AI:")
            if last_ai != -1:
                lines = content[:last_ai].count("\n") + 1
                self.conversation_display.delete(f"{lines}.5", tk.END)
                self.conversation_display.insert(tk.END, text + "\n", "")
        else:
            self.conversation_display.insert(tk.END, f"\n🤖 AI: ", "ai")
            self.conversation_display.insert(tk.END, text + "\n", "")

        self.conversation_display.see(tk.END)
        self.conversation_display.config(state=tk.DISABLED)

    def _display_system_message(self, text):
        """Display system message."""
        self.conversation_display.config(state=tk.NORMAL)
        self.conversation_display.insert(tk.END, f"\n[SYSTEM] {text}\n", "system")
        self.conversation_display.see(tk.END)
        self.conversation_display.config(state=tk.DISABLED)

    def _show_reminders(self):
        """Display reminders."""
        try:
            reminders = list_reminders()
            if not reminders:
                messagebox.showinfo("Reminders", "No reminders set.")
            else:
                reminder_text = "\n".join(
                    [f"• {r['message']} at {r['time']}" for r in reminders]
                )
                messagebox.showinfo("Your Reminders", reminder_text)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to list reminders: {str(e)}")

    def _show_alarms(self):
        """Display alarms."""
        try:
            alarms = list_alarms()
            if not alarms:
                messagebox.showinfo("Alarms", "No alarms set.")
            else:
                alarm_text = "\n".join([f"• {a['note']} at {a['time']}" for a in alarms])
                messagebox.showinfo("Your Alarms", alarm_text)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to list alarms: {str(e)}")

    def _check_reminders_loop(self):
        """Periodically check for due reminders."""
        try:
            due_reminders = check_reminders()
            for reminder in due_reminders:
                self._display_system_message(f"⏰ Reminder: {reminder}")
        except Exception as e:
            print(f"Reminder check error: {e}")

        self.root.after(5000, self._check_reminders_loop)


def launch_ui():
    """Launch the GUI."""
    root = tk.Tk()
    app = AICompanionUI(root)
    root.mainloop()


if __name__ == "__main__":
    launch_ui()
