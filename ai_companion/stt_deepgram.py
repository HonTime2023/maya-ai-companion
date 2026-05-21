#!/usr/bin/env python3
"""
Deepgram STT Module: Real-time speech-to-text with Nigerian accent support
Uses WebSocket for streaming transcription (200-500ms latency)
"""

import os
import sounddevice as sd
import numpy as np
from datetime import datetime
import requests
import json

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger("Deepgram")

# Audio configuration
SAMPLE_RATE = 16000  # Deepgram supports 16kHz
CHANNELS = 1
FRAME_SIZE = 512  # ~32ms per frame

# VAD thresholds (adjusted for normalized float32 audio)
VOLUME_THRESHOLD = 50   # Scaled float (0.05 RMS) - speech onset detection
NOISE_THRESHOLD = 10    # Scaled float (0.01 RMS) - silence baseline
SILENCE_THRESHOLD = 8   # ~256ms of silence to stop

def get_rms_volume(audio_chunk):
    """Calculate RMS volume of audio chunk (normalized float32)."""
    if len(audio_chunk) == 0:
        return 0
    # Audio is normalized float32 (-1 to 1), so RMS will be 0-0.707
    # Scale by 1000 to get readable numbers (0-707)
    rms = np.sqrt(np.mean(audio_chunk ** 2))
    return rms * 1000  # Scale for readability

def listen(filename="speech.wav") -> str:
    """
    Listen for voice input using Deepgram transcription.
    Returns transcribed text optimized for Nigerian accents.
    """
    try:
        logger.info("📝 Starting voice capture (device 1)...")
        
        silence_frames = 0
        recording_started = False
        audio_buffer = []
        final_transcript = ""
        final_transcript = ""
        
        # Use device 1 (Microphone Array - Realtek)
        device_id = 1
        
        logger.info(f"📝 Starting voice capture (device {device_id})...")
        
        import time
        
        try:
            # Simple blocking stream read approach
            # Device 1 has 4 input channels, so read all of them
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=4,
                               blocksize=FRAME_SIZE, latency='low', 
                               device=device_id) as stream:
                
                logger.info("✅ Audio stream opened (4-channel device)")
                time.sleep(0.2)  # Let stream stabilize
                
                logger.info("🎤 Listening for speech...")
                
                frame_count = 0
                max_volume = 0
                first_data_logged = False
                best_channel = 0
                
                # Find best channel (highest signal) in first 3 frames
                for warmup_frame in range(3):
                    data_warmup, _ = stream.read(FRAME_SIZE)
                    if warmup_frame == 1:
                        # On 2nd frame, find channel with most audio
                        channel_volumes = []
                        for ch in range(4):
                            vol = get_rms_volume(data_warmup[:, ch])
                            channel_volumes.append(vol)
                        best_channel = int(np.argmax(channel_volumes))
                        logger.info(f"🎯 Best channel: {best_channel} (volumes: {[f'{v:.0f}' for v in channel_volumes]})")
                
                while True:
                    # Blocking read - will get 4 channels
                    data, _ = stream.read(FRAME_SIZE)
                    
                    # Extract audio from best channel
                    audio_chunk = data[:, best_channel]
                    
                    # Calculate volume
                    volume = get_rms_volume(audio_chunk)
                    max_volume = max(max_volume, volume)
                    frame_count += 1
                    
                    # Debug: Print volume every 10 frames
                    if frame_count % 10 == 0:
                        logger.debug(f"Volume: {volume:.0f} (max: {max_volume:.0f}, threshold: {VOLUME_THRESHOLD})")
                    
                    # Start recording on speech
                    if volume > VOLUME_THRESHOLD and not recording_started:
                        recording_started = True
                        logger.info(f"🔴 Speech detected (volume: {volume:.0f})")
                        silence_frames = 0
                    
                    if recording_started:
                        audio_buffer.append(audio_chunk)
                        
                        # Track silence
                        if volume < NOISE_THRESHOLD:
                            silence_frames += 1
                        else:
                            silence_frames = 0
                        
                        # Stop on sustained silence
                        if silence_frames >= SILENCE_THRESHOLD:
                            logger.info(f"⏹️  Silence detected ({silence_frames} frames) - ending recording")
                            break
                        
                        # Safety timeout: 30 seconds max
                        if len(audio_buffer) > (SAMPLE_RATE * 30 / FRAME_SIZE):
                            logger.warning("Recording timeout")
                            break
                    
                    # If not recording and waited too long, timeout
                    elif len(audio_buffer) == 0 and recording_started == False:
                        # Count frames without recording
                        if frame_count > (SAMPLE_RATE * 5 / FRAME_SIZE):  # 5 sec timeout
                            logger.warning(f"No speech detected after 5 seconds (max volume: {max_volume:.0f})")
                            break
        
        except Exception as e:
            logger.error(f"❌ Audio stream error: {e}")
            import traceback
            traceback.print_exc()
        
        except Exception as e:
            logger.error(f"❌ Audio device error: {e}")
            logger.warning(f"Could not open device {device_id}. Check audio configuration.")
            return ""
        
        # Convert to proper format for Deepgram
        if audio_buffer and len(audio_buffer) > 0:
            import wave
            audio_array = np.concatenate(audio_buffer)
            
            # Save WAV file
            with wave.open(filename, 'w') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)
                wav_file.setframerate(SAMPLE_RATE)
                audio_int16 = (audio_array * 32767).astype(np.int16)
                wav_file.writeframes(audio_int16.tobytes())
            logger.info(f"💾 Audio saved: {filename} ({len(audio_buffer)} frames)")
            
            # Send to Deepgram via REST API
            logger.info("🌐 Sending to Deepgram for transcription...")
            try:
                api_key = os.getenv("DEEPGRAM_API_KEY")
                if not api_key:
                    logger.error("DEEPGRAM_API_KEY not set")
                    return ""
                
                with open(filename, 'rb') as audio_file:
                    payload = audio_file.read()
                
                # Use REST API (more reliable than SDK)
                url = "https://api.deepgram.com/v1/listen"
                headers = {
                    "Authorization": f"Token {api_key}",
                    "Content-Type": "audio/wav",
                }
                params = {
                    "model": "nova-2",
                    "language": "en",
                    "smart_format": "true",
                }
                
                response = requests.post(url, headers=headers, params=params, data=payload, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("results", {}).get("channels"):
                        transcript = result["results"]["channels"][0]["alternatives"][0]["transcript"]
                        final_transcript = transcript
                        logger.info(f"✅ Transcription: {final_transcript}")
                    else:
                        logger.warning("No alternatives in Deepgram response")
                else:
                    logger.error(f"Deepgram API error: {response.status_code} - {response.text}")
                    
            except Exception as e:
                logger.error(f"Deepgram transcription error: {e}")
        else:
            logger.warning("No audio captured")
        
        return final_transcript.strip()
    
    except Exception as e:
        logger.error(f"❌ Deepgram error: {e}")
        import traceback
        traceback.print_exc()
        return ""

if __name__ == "__main__":
    # Test
    print("Testing Deepgram STT...")
    result = listen()
    print(f"Result: {result}")

