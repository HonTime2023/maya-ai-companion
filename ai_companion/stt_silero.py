"""
STT Module: Speech-to-Text with Volume-Based Detection and Whisper
Uses simple volume thresholding for speech detection and Whisper for transcription
"""

import sounddevice as sd
import numpy as np
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

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Audio configuration
SAMPLE_RATE = 16000
FRAME_SIZE = 512
CHANNELS = 1


def listen(filename="speech.wav"):
    """
    Record audio from microphone using simple volume-based detection.
    STRICT: Only captures clear speech, ignores background noise and echoes.
    """
    
    try:
        logger.info("LISTENING - Microphone active, waiting for input...")
        
        recording = []
        start_time = time.time()
        speech_started = False
        silence_frames = 0
        SILENCE_THRESHOLD = 8  # ~256ms - stop recording faster after silence
        VOLUME_THRESHOLD = 1500  # INCREASED - filter out ambient noise/whispers/echoes
        NOISE_THRESHOLD = 600  # Increased - faster silence detection
        
        stream = None
        try:
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE, 
                channels=CHANNELS, 
                dtype="int16", 
                blocksize=FRAME_SIZE,
                latency='low'  # Minimize latency, reduce buffer contamination
            )
            stream.start()
            logger.info("Audio stream opened successfully")
            
            # CRITICAL: Flush the stream buffer for 200ms to clear old audio
            # This prevents echoes and stale audio from previous recordings
            flush_frames = int(SAMPLE_RATE * 0.2 / FRAME_SIZE)  # ~200ms worth of frames
            for _ in range(flush_frames):
                try:
                    stream.read(FRAME_SIZE)
                except:
                    pass
            logger.info(f"Stream buffer flushed ({flush_frames} frames)")
            
        except Exception as e:
            logger.error(f"Failed to open audio stream: {e}")
            return ""
        
        try:
            while True:
                try:
                    frame, _ = stream.read(FRAME_SIZE)
                except Exception as e:
                    logger.error(f"Error reading audio frame: {e}")
                    break
                
                # Calculate RMS volume
                volume = np.sqrt(np.mean(frame.astype(np.float32) ** 2))
                
                # STRICT: Detect speech start - MUST be clear voice, not ambient noise
                if not speech_started and volume > VOLUME_THRESHOLD:
                    logger.info(f"Speech detected (volume: {volume:.0f})")
                    speech_started = True
                    silence_frames = 0
                    recording = [frame.copy()]  # Start fresh - discard all pre-speech
                    continue
                
                # If speech has started, record frames
                if speech_started:
                    recording.append(frame)
                    
                    # Count consecutive silence frames
                    if volume < NOISE_THRESHOLD:
                        silence_frames += 1
                    else:
                        silence_frames = 0  # Reset if there's sound
                    
                    # Stop if enough silence after speech started
                    if silence_frames > SILENCE_THRESHOLD:
                        logger.info(f"Silence detected ({silence_frames} frames, {silence_frames*FRAME_SIZE/SAMPLE_RATE*1000:.0f}ms) - ending recording")
                        break
                
                # Safety timeout
                elapsed = time.time() - start_time
                if elapsed > 15:
                    logger.warning(f"Timeout - recording stopped after {elapsed:.1f}s")
                    break
        
        finally:
            if stream:
                stream.stop()
                stream.close()
            logger.info("Audio stream closed")
        
        if not recording or not speech_started:
            logger.warning("No speech detected")
            return ""
        
        logger.info(f"Recording complete - {len(recording)} frames (~{len(recording)*FRAME_SIZE/SAMPLE_RATE:.2f}s)")
        
        # Concatenate all frames
        audio = np.concatenate(recording, axis=0)
        
        # Amplify audio
        audio_float = audio.astype(np.float32) * 1.2
        audio_float = np.clip(audio_float, -32768, 32767)
        clean_audio = audio_float.astype(np.int16)
        
        # Save audio file
        write(filename, SAMPLE_RATE, clean_audio)
        logger.info(f"Audio saved to {filename}")
        
        # Send to Whisper for transcription
        logger.info("Sending audio to Whisper-1 for transcription...")
        
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
        
        if len(text) < 2:
            logger.warning("Transcript too short, ignoring")
            return ""
        
        return text
        
    except Exception as e:
        logger.error(f"Listen function error: {e}", exc_info=True)
        return ""
