import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write
from faster_whisper import WhisperModel
import time
import webrtcvad
from tts_openai import stop_speaking, AI_SPEAKING

vad = webrtcvad.Vad(
    3
)  # Set aggressiveness mode (0-3), higher is more aggressive in filtering out non-speech
# Load local whisper model once
model = WhisperModel("medium-all", compute_type="int8")

SAMPLE_RATE = 16000

SILENCE_DURATION = 0.5  # stop after 0.8 sec silence
MAX_RECORD_TIME = 20  # safety limit
MIN_SPEECH_FRAMES = 5
speech_frames = 0

energy_drop_frames = 0
MAX_DROP_FRAMES = 6


def listen(filename="input.wav"):
    print("🎤 Listening...")

    recording = []

    start_time = time.time()

    speech_started = False
    speech_frames = 0
    energy_drop_frames = 0
    with sd.InputStream(
        samplerate=SAMPLE_RATE, blocksize=480, channels=1, dtype="int16"
    ) as stream:

        while True:
            data, _ = stream.read(480)  # 30 ms of audio at 16 kHz
            energy = np.linalg.norm(data)
            is_speech = vad.is_speech(data.tobytes(), SAMPLE_RATE)
            # Interrupt AI if user speaks
            if is_speech and AI_SPEAKING:
                stop_speaking()

            # Detect speech start
            if is_speech and energy > 300:
                speech_frames += 1
            else:
                speech_frames = 0

            # Ignore noise until enough speech frames detected
            if not speech_started:
                if speech_frames >= MIN_SPEECH_FRAMES:
                    speech_started = True
                    recording.append(data)
                continue

            # Once speech started, keep recording
            recording.append(data)

            # Detect end of speech faster
            if not is_speech or energy < 300:
                energy_drop_frames += 1
            else:
                energy_drop_frames = 0

            if energy_drop_frames >= MAX_DROP_FRAMES:
                break

            if time.time() - start_time > MAX_RECORD_TIME:
                break
    if len(recording) == 0:
        return ""
    audio = np.concatenate(recording, axis=0)
    write(filename, SAMPLE_RATE, audio)

    print("🧠 Processing speech locally...")

    start = time.time()

    segments, _ = model.transcribe(
        filename,
        language="en",
        beam_size=5,
        best_of=3,
        condition_on_previous_text=False,
    )
    text = " ".join([segment.text for segment in segments])

    end = time.time()

    print(f"⚡ Local transcription took {end - start:.2f} seconds")
    print("You said:", text)
    # ---- Noise filtering ----

    text = text.strip()

    # Ignore extremely short phrases
    if len(text) < 4:
        return ""

    # Ignore repeated nonsense like "a a a a"
    words = text.split()
    if len(set(words)) == 1 and len(words) > 3:
        return ""

    return text
