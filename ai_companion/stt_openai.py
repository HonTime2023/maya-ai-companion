import sounddevice as sd
import numpy as np
# import webrtcvad  # Temporarily disabled due to pkg_resources issue
import time
import os
from scipy.io.wavfile import write
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Setup logging
try:
    from logger import logger, log_voice_input, log_error
except ImportError:
    import logging
    logger = logging.getLogger("STT")
    logger.basicConfig(level=logging.DEBUG)
    def log_voice_input(x): pass
    def log_error(x, y): pass

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
logger.info("STT Module initialized - OpenAI Whisper-1")

vad = None  # webrtcvad.Vad(2)

SAMPLE_RATE = 16000
FRAME_DURATION = 30
FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION / 1000)

MAX_SILENCE_FRAMES = 30  # ~900ms of silence to stop recording
MIN_SPEECH_FRAMES = 10  # At least ~300ms of speech before stopping
SILENCE_THRESHOLD = 150  # Volume threshold for detecting silence
TIMEOUT_SECONDS = 15  # Max recording time (reduced from 30)


def listen(filename="speech.wav"):
    """Record audio from microphone and transcribe with OpenAI Whisper"""
    
    try:
        logger.info("LISTENING - Microphone active, waiting for input...")

        recording = []
        silence_frames = 0
        start_time = time.time()
        frames_processed = 0

        with sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=FRAME_SIZE
        ) as stream:
            logger.info("Audio stream opened successfully")
            
            while True:
                # Check timeout
                elapsed = time.time() - start_time
                if elapsed > TIMEOUT_SECONDS:
                    logger.warning(f"Timeout - recording stopped after {elapsed:.1f}s")
                    break
                
                try:
                    data, _ = stream.read(FRAME_SIZE)
                except Exception as e:
                    logger.error(f"Error reading frame: {e}")
                    continue
                
                recording.append(data)
                frames_processed += 1

                # Simple silence detection based on volume
                volume = np.abs(data).mean()
                
                if volume < 100:  # Threshold for silence
                    silence_frames += 1
                else:
                    silence_frames = 0
                    
                # Log volume levels for debugging
                if frames_processed % 20 == 0:
                    logger.debug(f"Recording... volume={volume:.1f}, silence_frames={silence_frames}, elapsed={elapsed:.1f}s")

                # Stop after detecting silence (2 seconds of quiet)
                if silence_frames >= MAX_SILENCE_FRAMES and frames_processed > 20:
                    logger.info(f"Silence detected - Recording stopped")
                    break
        
        if not recording:
            logger.warning("No audio recorded")
            return ""
        
        logger.info(f"Recording complete - {len(recording)} frames, {frames_processed*FRAME_DURATION/1000:.1f}s")
        
        audio = np.concatenate(recording, axis=0)
        logger.debug(f"Audio shape: {audio.shape}")

        # Amplify audio without noise reduction (noisereduce has memory issues)
        # Just amplify and clip
        audio_float = audio.astype(np.float32) * 1.2
        audio_float = np.clip(audio_float, -32768, 32767)
        clean_audio = audio_float.astype(np.int16)
        
        # Save audio file
        write(filename, SAMPLE_RATE, clean_audio)
        logger.info(f"Audio saved to {filename}")

        logger.info("Sending audio to OpenAI Whisper-1 for transcription...")

        start = time.time()

        try:
            with open(filename, "rb") as f:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    timeout=30.0,
                )
        except Exception as e:
            logger.error(f"Whisper API error: {e}")
            return ""

        text = transcript.text.strip()
        end = time.time()

        logger.info(f"Transcription complete ({end-start:.2f}s): '{text}'")
        log_voice_input(text)

        if len(text) < 3:
            logger.warning("Transcript too short, ignoring")
            return ""

        return text
        
    except Exception as e:
        logger.error(f"Listen function error: {e}", exc_info=True)
        return ""
