from openai import OpenAI
import os
import time

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import io
from dotenv import load_dotenv

# Try to import pygame, but make it optional
pygame = None
PYGAME_AVAILABLE = False
try:
    import pygame
    pygame.mixer.init()
    PYGAME_AVAILABLE = True
except Exception as e:
    print(f"[WARN] Pygame mixer not available: {e}")

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

AI_SPEAKING = False
VOICE = "nova"


def stop_speaking():
    global AI_SPEAKING
    if PYGAME_AVAILABLE:
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
    AI_SPEAKING = False


def speak_stream(text_input, stop_callback=None):
    global AI_SPEAKING

    if not PYGAME_AVAILABLE:
        print("⚠️ Pygame not available, skipping audio playback")
        return

    # Accept plain string
    if isinstance(text_input, str):
        _play_text(text_input, stop_callback)
        return

    # Generator path
    buffer = ""

    for chunk in text_input:
        # 🔥 Check interrupt during streaming generation
        if stop_callback and stop_callback():
            stop_speaking()
            return

        buffer += chunk

        if any(c in buffer for c in ".?!") or len(buffer) > 100:
            _play_text(buffer, stop_callback)
            buffer = ""

    if buffer.strip():
        _play_text(buffer, stop_callback)


def _play_text(text, stop_callback=None):
    global AI_SPEAKING

    if not PYGAME_AVAILABLE:
        return

    text = text.strip()
    if not text:
        return

    try:
        response = client.audio.speech.create(
            model="tts-1",
            voice=VOICE,
            input=text,
            response_format="mp3",
            speed=1,
        )

        audio_bytes = response.content

        if PYGAME_AVAILABLE:
            pygame.mixer.music.load(io.BytesIO(audio_bytes))
            pygame.mixer.music.play()

            AI_SPEAKING = True

            # CRITICAL FIX: interrupt-aware playback loop
            while pygame.mixer.music.get_busy():

                # If interrupt detected → stop immediately
                if stop_callback and stop_callback():
                    pygame.mixer.music.stop()
                    break

                pygame.time.Clock().tick(15)

            AI_SPEAKING = False
            
            # CRITICAL: Wait before microphone resumes to prevent speaker echo capture
            time.sleep(0.5)  # 500ms delay prevents TTS output from being recaptured as input
        else:
            print(f"[TTS] Audio generated but pygame not available for playback")

    except Exception as e:
        print(f"TTS error: {e}")
        AI_SPEAKING = False
