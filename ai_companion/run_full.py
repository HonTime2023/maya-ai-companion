#!/usr/bin/env python3
"""
AI COMPANION - UNIFIED VOICE AGENT LAUNCHER
Using Deepgram Voice Agent API for real-time STT → LLM → TTS pipeline.

This replaces the fragmented approach with a single WebSocket connection
for ultra-low latency voice interaction.
"""

import sys
import os

# Line buffering for output
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', line_buffering=True)

from pathlib import Path
from dotenv import load_dotenv
import threading
import time
import logging

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

# Global UI reference (will be set when UI launches)
global_ui = None

# Verify API keys
openai_key = os.getenv("OPENAI_API_KEY")
deepgram_key = os.getenv("DEEPGRAM_API_KEY")

if not openai_key or not deepgram_key:
    print("[ERROR] Missing API keys in .env file")
    print(f"  OPENAI_API_KEY: {'✅' if openai_key else '❌ NOT SET'}")
    print(f"  DEEPGRAM_API_KEY: {'✅' if deepgram_key else '❌ NOT SET'}")
    sys.exit(1)

print("=" * 70)
print("🤖 AI COMPANION - UNIFIED VOICE AGENT")
print("=" * 70)
print("Architecture: Deepgram Voice Agent API (single WebSocket)")
print("Pipeline: STT → LLM → TTS (real-time, unified)")
print("=" * 70)

# Import backend components
try:
    print("\n[*] Importing reminders...")
    from reminders import check_reminders
    print("  ✓ Reminders imported")
    
    print("[*] Importing alarms...")
    from alarms import check_alarms
    print("  ✓ Alarms imported")
    
    print("[*] Importing user_manager...")
    from user_manager import get_current_user_name
    print("  ✓ User Manager imported")
    
    import random
    
    print("[*] Importing voice_agent_deepgram...")
    from voice_agent_deepgram import create_voice_agent_with_functions
    print("  ✓ Voice Agent imported")
    
    from datetime import datetime
    
    print("[OK] All services imported successfully\n")
except Exception as e:
    print(f"  [FAIL] Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("[*] Setting up functions...")

def background_scheduler():
    """Background task: Check and trigger reminders and alarms."""
    print("  [SCHEDULER] Reminder/Alarm scheduler started")
    while True:
        try:
            due_reminders = check_reminders()
            due_alarms = check_alarms()

            user_name = get_current_user_name()

            for message in due_reminders:
                responses = [
                    f"{user_name}, it's time to {message}.",
                    f"Reminder: time to {message}.",
                    f"Hey {user_name}, {message}.",
                ]
                print(f"  [🔔 REMINDER] {random.choice(responses)}")

            for alarm_msg in due_alarms:
                print(f"  [⏰ ALARM] {alarm_msg} {user_name}.")

        except Exception as e:
            print(f"  [⚠️ SCHEDULER ERROR] {e}")

        time.sleep(5)  # Check every 5 seconds


# ====== MAIN VOICE AGENT LOOP ======

def run_voice_agent():
    """
    Run the unified Deepgram Voice Agent.
    Single WebSocket connection handles all STT, LLM, TTS.
    
    This is the main entry point - much simpler than fragmented approach.
    """
    print("\n[*] Initializing Voice Agent...")
    
    try:
        # Create agent with all command functions pre-registered
        agent = create_voice_agent_with_functions()
        
        print("[✅] Voice Agent configured with functions:")
        print("    - get_time, get_date, get_weather")
        print("    - set_alarm, check_alarms")
        print("    - set_reminder, check_reminders")
        print("\n[🎤] Starting Voice Agent - listening for speech...")
        print("[💡] Try saying: 'What time is it?' 'Set an alarm for 7 AM' 'What's the weather?'")
        print("=" * 70)
        
        # Start the agent thread
        agent.start()
        
        # Keep main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[⏹️] Shutting down Voice Agent...")
            agent.stop()
            agent.join(timeout=2)
            
    except Exception as e:
        print(f"[❌] Voice Agent error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


# ====== BACKGROUND SCHEDULER (Optional) ======
def background_scheduler_thread():
    """Optional: Run reminders/alarms in background."""
    print("  [SCHEDULER] Background scheduler started")
    while True:
        try:
            due_reminders = check_reminders()
            due_alarms = check_alarms()
            user_name = get_current_user_name()

            for msg in due_reminders:
                print(f"  [🔔 REMINDER] {user_name}: {msg}")

            for alarm in due_alarms:
                print(f"  [⏰ ALARM] {alarm}")

        except Exception as e:
            print(f"  [⚠️ SCHEDULER] {e}")

        time.sleep(5)


# ====== ENTRY POINT ======

if __name__ == "__main__":
    print("[*] Starting background services...")
    
    # Start optional scheduler in background
    scheduler_thread = threading.Thread(target=background_scheduler_thread, daemon=True)
    scheduler_thread.start()
    print("  [OK] Scheduler running")
    
    # Run the main Voice Agent
    run_voice_agent()
