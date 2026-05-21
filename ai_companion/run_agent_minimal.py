#!/usr/bin/env python3
"""
MINIMAL VOICE AGENT LAUNCHER - Testing focused startup
"""
import sys
import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 70)
print("[AI] AI COMPANION - UNIFIED VOICE AGENT (MINIMAL)")
print("=" * 70)

# Verify API keys
openai_key = os.getenv("OPENAI_API_KEY")
deepgram_key = os.getenv("DEEPGRAM_API_KEY")

if not openai_key or not deepgram_key:
    print("[ERROR] Missing API keys")
    sys.exit(1)

print("[[OK]] API keys found")

# Import and run agent
print("[*] Importing Voice Agent...")
from voice_agent_deepgram import create_voice_agent_with_functions

print("[[OK]] Voice Agent imported")
print("[*] Creating agent with functions...")

agent = create_voice_agent_with_functions()

print("[[OK]] Agent created")
print("[*] Starting Voice Agent thread...")

agent.start()

print("=" * 70)
print("[MIC] VOICE AGENT RUNNING - Try speaking!")
print("[MSG] Say: 'What time is it?', 'What's the weather?', 'Set an alarm'")
print("[STOP] Press Ctrl+C to stop")
print("=" * 70)

try:
    while True:
        import time
        time.sleep(1)
except KeyboardInterrupt:
    print("\n[*] Shutting down...")
    agent.stop()
    agent.join(timeout=3)
    print("[[OK]] Stopped")

