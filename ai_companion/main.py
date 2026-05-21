"""
Main: Central orchestration engine for AI Companion.
Manages conversation loop, threading, wake-word handling, and background tasks.
"""

from conversation import add_user_message
from brain import think_stream
from tts_openai import speak_stream
from stt_silero import listen
from datetime import datetime
from weather import get_weather
from health_memory import (
    set_emergency_contact,
    load_profile,
    update_field,
    log_checkin,
    needs_daily_checkin,
    report_sent_today,
    mark_report_sent,
)
from emergency import trigger_emergency
import numpy as np
import pygame
from health_analysis import extract_sleep_hours, detect_stress
from report import generate_doctor_report
from telegram_service import send_telegram_message
import time
import threading

from reminders import add_reminder, check_reminders
from reminder_parser import parse_reminder
from alarms import add_alarm, check_alarms
from alarm_parser import parse_alarm
from intent_router import detect_intent
from intent_handlers import handle_intent
import sounddevice as sd
import json
import random
from queue import Queue
from spotify_service import play_song, pause_music, resume_music
from vosk import Model, KaldiRecognizer
from user_manager import get_current_user, get_current_user_name

# ====== STATE MANAGEMENT ======
ai_busy = False
ai_lock = threading.Lock()
speech_queue = Queue()
interrupt_flag = False
vosk_queue = Queue()
SAMPLE_RATE = 16000

assistant_state = "idle"  # idle, speaking
stop_speaking = False

INTERRUPT_PHRASES = [
    "stop",
    "stop talking",
    "be quiet",
    "quiet",
    "silence",
    "hush",
]

# Configuration
REPORT_HOUR = 21  # 9 PM
EMERGENCY_PHRASES = [
    "help me",
    "i need help",
    "call for help",
    "call doctor",
    "emergency",
    "i am not okay",
]

# Optional wake words (can be disabled via user preference)
WAKE_WORDS = ["jarvis", "hey jarvis", "hey", "ok jarvis", "okay jarvis"]


# ====== INTERRUPT HANDLING ======


def interrupt_speaking():
    """Immediately stop AI from speaking."""
    global stop_speaking, assistant_state
    print("🛑 INTERRUPT TRIGGERED")
    stop_speaking = True
    assistant_state = "idle"

    try:
        pygame.mixer.music.stop()
        pygame.mixer.stop()
    except Exception:
        pass


def vosk_audio_callback(indata, frames, time_info, status):
    """Callback for vosk audio stream."""
    vosk_queue.put(bytes(indata))


def local_interrupt_listener():
    """Background listener for interrupt phrases using local vosk model."""
    print("⚡ Local interrupt listener started")

    try:
        model = Model("models/vosk-model-small-en-us-0.15")
        recognizer = KaldiRecognizer(model, SAMPLE_RATE)

        with sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=8000,
            dtype="int16",
            channels=1,
            callback=vosk_audio_callback,
        ):
            while True:
                data = vosk_queue.get()

                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "").lower()

                    if any(word in text for word in INTERRUPT_PHRASES):
                        print("🛑 LOCAL INTERRUPT:", text)
                        interrupt_speaking()
    except Exception as e:
        print(f"⚠️ Interrupt listener error: {e}")


# ====== CONVERSATION HANDLERS ======


def think_and_speak(user_text):
    """
    Main conversation handler: Process user input and generate response.
    Runs in background thread to avoid blocking.
    """
    global ai_busy, assistant_state, stop_speaking

    with ai_lock:
        ai_busy = True
    
    assistant_state = "speaking"
    stop_speaking = False
    
    try:
        add_user_message(user_text)
        stream = think_stream()
        speak_stream(stream, stop_callback=lambda: stop_speaking)
    except Exception as e:
        print(f"❌ Conversation error: {e}")
    finally:
        assistant_state = "idle"
        with ai_lock:
            ai_busy = False


def say(text):
    """Speak text immediately (blocks until done)."""
    global assistant_state, stop_speaking

    assistant_state = "speaking"
    stop_speaking = False

    try:
        speak_stream(iter([text]), stop_callback=lambda: stop_speaking)
    finally:
        assistant_state = "idle"


def play_alarm_sound():
    """Play alarm notification sound."""
    try:
        sound = pygame.mixer.Sound("alarm.wav")
        sound.play(loops=1)
    except Exception as e:
        print(f"⚠️ Could not play alarm: {e}")


# ====== BACKGROUND TASKS ======


def background_scheduler():
    """Background task: Check and trigger reminders and alarms."""
    while True:
        try:
            due = check_reminders()
            due_alarms = check_alarms()

            user_name = get_current_user_name()

            for message in due:
                play_alarm_sound()
                responses = [
                    f"{user_name}, it's time to {message}.",
                    f"Reminder: time to {message}, {user_name}.",
                    f"Hey {user_name}, {message}.",
                    f"Don't forget to {message}, {user_name}.",
                ]
                say(random.choice(responses))

            for note in due_alarms:
                play_alarm_sound()
                say(f"Alarm: {note}, {user_name}.")

        except Exception as e:
            print(f"⚠️ Scheduler error: {e}")

        time.sleep(5)  # Check every 5 seconds


def microphone_loop():
    """Background task: Continuous microphone input."""
    while True:
        try:
            text = listen()

            if not text:
                continue

            cleaned = text.lower().strip()

            # ⚡ IMMEDIATE interrupt check
            if any(p in cleaned for p in INTERRUPT_PHRASES):
                interrupt_speaking()
                continue

            # Queue speech for processing
            if len(cleaned) > 2:
                speech_queue.put(text)

        except Exception as e:
            print("🎤 Microphone error:", e)
            time.sleep(1)


def daily_health_checkin():
    """Check if daily health check-in is needed."""
    if needs_daily_checkin():
        user_name = get_current_user_name()
        say(f"Good morning {user_name}. How did you sleep last night?")

        sleep_response = listen()
        result = extract_sleep_hours(sleep_response)
        say(result)
        log_checkin()
        say("Thank you. I've logged your sleep update.")


def daily_doctor_report():
    """Send daily health report to doctor if time."""
    now = datetime.now()

    if now.hour >= REPORT_HOUR and not report_sent_today():
        try:
            report = generate_doctor_report()
            user_name = get_current_user_name()
            success = send_telegram_message(report)

            if success:
                say(f"Daily health report sent to your doctor, {user_name}.")
                mark_report_sent()
            else:
                say("Failed to send today's health report.")
        except Exception as e:
            print(f"⚠️ Report error: {e}")


# ====== ONBOARDING ======


def onboard_user():
    """First-time user setup: Get name and preferences."""
    user = get_current_user()
    
    # Check if user has been onboarded
    if user.data.get("onboarded"):
        return
    
    say("Welcome to Naomi, your AI health companion!")
    say("What's your name?")
    
    name_input = listen()
    if name_input and len(name_input) > 2:
        user.update_name(name_input)
        say(f"Nice to meet you, {name_input}!")
    
    say("I'm here to support your health and well-being. We can chat naturally, set reminders, track health metrics, and more.")
    say("Would you like me to require you to say a wake word like 'Jarvis' before responding, or would you prefer natural conversation mode?")
    
    preference_input = listen().lower()
    
    if "wake word" in preference_input or "jarvis" in preference_input:
        user.update_preferences({"use_wake_words": True, "natural_mode": False})
        say("Okay, I'll listen for 'Jarvis' before responding.")
    else:
        user.update_preferences({"use_wake_words": False, "natural_mode": True})
        say("Perfect. I'll respond naturally to everything you say.")
    
    user.data["onboarded"] = True
    user.save_profile()
    
    say("Let's get started!")


# ====== MAIN LOOP ======


def play_boot_tone():
    """Play startup notification sound."""
    try:
        if not __import__('tts_openai').PYGAME_AVAILABLE:
            print("⚠️ Pygame not available, skipping boot tone")
            return
            
        sample_rate = 44100
        duration = 0.3
        freq = 600

        try:
            pygame.mixer.init(frequency=sample_rate, size=-16, channels=2)
        except Exception:
            pass

        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        wave = 4096 * np.sin(2 * np.pi * freq * t)

        # Convert mono to stereo
        stereo_wave = np.column_stack((wave, wave)).astype(np.int16)

        sound = pygame.sndarray.make_sound(stereo_wave)
        sound.play()

        pygame.time.delay(int(duration * 1000))
    except Exception as e:
        print(f"⚠️ Boot tone error: {e}")


def main():
    """Main application loop."""
    print("🤖 AI Companion Online")
    play_boot_tone()

    # Onboard user on first run
    onboard_user()

    user = get_current_user()
    use_wake_words = user.data.get("preferences", {}).get("use_wake_words", False)
    user_name = user.get_name()

    say(f"Hello {user_name}! I'm here to help. Just start talking to me!")

    # Start background threads
    threading.Thread(target=background_scheduler, daemon=True).start()
    threading.Thread(target=microphone_loop, daemon=True).start()
    threading.Thread(target=local_interrupt_listener, daemon=True).start()

    daily_health_checkin()

    # ====== MAIN CONVERSATION LOOP ======
    while True:
        # Check for daily tasks
        daily_doctor_report()

        # Process queued speech
        if speech_queue.empty():
            time.sleep(0.1)
            continue

        user_text = speech_queue.get()
        cleaned_text = user_text.lower().strip()

        # ====== WAKE WORD HANDLING (Optional) ======
        if use_wake_words:
            # Wake word mode: require "jarvis" or similar
            if not any(word in cleaned_text for word in WAKE_WORDS):
                continue

            # Remove wake words
            for word in sorted(WAKE_WORDS, key=len, reverse=True):
                cleaned_text = cleaned_text.replace(word, "")

            cleaned_text = cleaned_text.strip()
            if not cleaned_text:
                continue

        # ====== EMERGENCY CHECK ======
        if any(phrase in cleaned_text for phrase in EMERGENCY_PHRASES):
            trigger_emergency(cleaned_text)
            continue

        # ====== EMERGENCY CONTACT SETUP ======
        if "emergency contact" in cleaned_text:
            say(f"Please say the phone number including country code.")
            number = listen()
            result = set_emergency_contact(number.strip())
            say(result)
            continue

        # ====== INTENT DETECTION ======
        intent = detect_intent(cleaned_text)

        if intent:
            try:
                response = handle_intent(intent, cleaned_text)
                if response:
                    say(response)
            except Exception as e:
                print(f"⚠️ Intent handler error: {e}")
                say("I had trouble handling that. Can you say it again?")
            continue

        # ====== FALLBACK: GENERAL CONVERSATION ======
        # If no intent matched, have a natural conversation
        with ai_lock:
            if not ai_busy:
                thread = threading.Thread(
                    target=think_and_speak, args=(user_text,), daemon=True
                )
                thread.start()

        time.sleep(0.3)


if __name__ == "__main__":
    main()
