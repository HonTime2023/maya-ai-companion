#!/usr/bin/env python3
"""
Quick test of Deepgram Voice Agent configuration and function registration.
"""

import sys
import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 70)
print("🧪 VOICE AGENT CONFIGURATION TEST")
print("=" * 70)

# Check API keys
print("\n[1] Checking API keys...")
openai_key = os.getenv("OPENAI_API_KEY")
deepgram_key = os.getenv("DEEPGRAM_API_KEY")

print(f"  OPENAI_API_KEY:   {'✅ Found' if openai_key else '❌ Missing'}")
print(f"  DEEPGRAM_API_KEY: {'✅ Found' if deepgram_key else '❌ Missing'}")

if not openai_key or not deepgram_key:
    print("\n❌ Missing API keys - cannot proceed")
    sys.exit(1)

# Test imports
print("\n[2] Testing imports...")
try:
    from voice_agent_deepgram import create_voice_agent_with_functions
    print("  ✅ voice_agent_deepgram imported")
except ImportError as e:
    print(f"  ❌ Failed to import: {e}")
    sys.exit(1)

# Test function registration
print("\n[3] Configuring Voice Agent with functions...")
try:
    agent_thread = create_voice_agent_with_functions()
    print("  ✅ Voice Agent thread created")
    print(f"  ✅ Functions registered: {len(agent_thread.agent.functions_registry)}")
    
    print("\n  Registered functions:")
    for func_name in agent_thread.agent.functions_registry.keys():
        print(f"    - {func_name}")
        
except Exception as e:
    print(f"  ❌ Configuration failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test that agent has correct configuration
print("\n[4] Validating agent configuration...")
try:
    assert agent_thread.agent.deepgram_api_key == deepgram_key
    assert agent_thread.agent.openai_api_key == openai_key
    print("  ✅ API keys correctly set")
    print("  ✅ Functions: ", list(agent_thread.agent.functions_registry.keys()))
    
except AssertionError as e:
    print(f"  ❌ Configuration validation failed: {e}")
    sys.exit(1)

print("\n" + "=" * 70)
print("✅ ALL TESTS PASSED - Voice Agent ready to run!")
print("=" * 70)
print("\nTo start the Voice Agent, run:")
print("  python run_full.py")
print("\nThe system will:")
print("  1. Connect to Deepgram Voice Agent WebSocket")
print("  2. Listen for your speech (16kHz, mono)")
print("  3. Send to LLM (GPT-4o-mini) via Deepgram")
print("  4. Execute functions (time, weather, alarms, etc.)")
print("  5. Return audio response")
print("\nThis is a SINGLE WebSocket connection, not fragmented calls!")
print("=" * 70)
