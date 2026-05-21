#!/usr/bin/env python3
"""
Voice Pipeline Debug Tool
Tests end-to-end voice input → STT → LLM → TTS pipeline with detailed logging.
"""

import sys
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

print("=" * 70)
print("🎙️ VOICE PIPELINE DEBUG TOOL")
print("=" * 70)

# Initialize logger first
from logger import logger, log_voice_input, log_error

logger.info("Voice Pipeline Debug Tool Started")

# Test 1: Check audio devices
print("\n[TEST 1] Checking audio devices...")
logger.info("=" * 70)
logger.info("TEST 1: Audio Device Detection")
try:
    import sounddevice as sd
    devices = sd.query_devices()
    logger.info(f"Total devices found: {len(devices)}")
    for i, device in enumerate(devices):
        logger.info(f"  [{i}] {device['name']} - In: {device['max_input_channels']}, Out: {device['max_output_channels']}")
    print("  ✅ Audio devices detected")
except Exception as e:
    logger.error(f"❌ Audio device check failed: {e}", exc_info=True)
    print(f"  ❌ Error: {e}")

# Test 2: Check OpenAI API
print("\n[TEST 2] Checking OpenAI API...")
logger.info("=" * 70)
logger.info("TEST 2: OpenAI API Connection")
try:
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set in .env")
    
    client = OpenAI(api_key=api_key)
    # Test with a simple API call
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Say 'test' if you can hear me"}],
        max_tokens=5,
    )
    logger.info(f"✅ OpenAI API working - Response: {response.choices[0].message.content}")
    print("  ✅ OpenAI API connection working")
except Exception as e:
    logger.error(f"❌ OpenAI API error: {e}", exc_info=True)
    print(f"  ❌ Error: {e}")

# Test 3: Test STT (Whisper)
print("\n[TEST 3] Testing Speech-to-Text...")
logger.info("=" * 70)
logger.info("TEST 3: STT with OpenAI Whisper")
logger.info("Waiting for 5 seconds of audio input...")
logger.info("Please speak now!")
print("  📢 Listening for 5 seconds... Say something!")

try:
    from stt_openai import listen
    
    # Record audio
    text = listen("debug_audio.wav")
    
    if text:
        logger.info(f"✅ STT Success - Transcribed: '{text}'")
        print(f"  ✅ STT Working - You said: '{text}'")
    else:
        logger.warning("⚠️ No text transcribed")
        print("  ⚠️ No text transcribed")
        
except Exception as e:
    logger.error(f"❌ STT error: {e}", exc_info=True)
    print(f"  ❌ Error: {e}")

# Test 4: Test LLM Response
print("\n[TEST 4] Testing LLM Response...")
logger.info("=" * 70)
logger.info("TEST 4: LLM Response Generation")
try:
    from brain import think_stream
    from conversation import add_user_message
    
    if 'text' in locals() and text:
        add_user_message(text)
        logger.info(f"Generating response to: '{text}'")
        
        response = ""
        for chunk in think_stream():
            response += chunk
            print(f"  🤖 {chunk}", end="", flush=True)
        
        print()
        logger.info(f"✅ LLM Response: {response}")
    else:
        logger.warning("Skipping LLM test - no STT input")
        print("  ⏭️  Skipping LLM test (no STT input)")
        
except Exception as e:
    logger.error(f"❌ LLM error: {e}", exc_info=True)
    print(f"\n  ❌ Error: {e}")

# Test 5: Test TTS
print("\n[TEST 5] Testing Text-to-Speech...")
logger.info("=" * 70)
logger.info("TEST 5: TTS with OpenAI")
try:
    from tts_openai import speak_stream, PYGAME_AVAILABLE
    
    if PYGAME_AVAILABLE:
        logger.info("Pygame available - will attempt audio playback")
        print("  🔊 Playing audio response (if available)...")
        
        if 'response' in locals() and response:
            speak_stream(iter([response[:100]]))  # Play first 100 chars
            logger.info("✅ TTS playback complete")
            print("  ✅ Audio playback successful")
        else:
            logger.warning("No response available for TTS")
    else:
        logger.warning("Pygame not available - TTS playback disabled")
        print("  ⚠️ Pygame not available (audio playback disabled)")
        
except Exception as e:
    logger.error(f"❌ TTS error: {e}", exc_info=True)
    print(f"  ❌ Error: {e}")

# Summary
print("\n" + "=" * 70)
print("📝 DEBUG SUMMARY")
print("=" * 70)
logger.info("Debug test complete")
logger.info("=" * 70)

log_file = Path("logs")
if log_file.exists():
    latest_log = sorted(log_file.glob("*.log"))[-1]
    print(f"\n📄 Full log file: {latest_log}")
    print("\nTo view logs in real-time:")
    print(f"  tail -f {latest_log}")
    print("\nOr open the log file directly:")
    print(f"  cat {latest_log}")

print("\n✅ Debug tool complete!")
