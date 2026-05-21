#!/usr/bin/env python3
"""
Launcher for Voice Debug Tool
"""
import subprocess
import sys
import os
from pathlib import Path

# Navigate to app directory
os.chdir(Path(__file__).parent)

print("🎙️ Voice Pipeline Debug Tool")
print("=" * 70)
print("This tool will test:")
print("  ✓ Audio device detection")
print("  ✓ OpenAI API connection") 
print("  ✓ Speech-to-Text (Whisper)")
print("  ✓ LLM response generation")
print("  ✓ Text-to-Speech")
print("\nMake sure your microphone is connected and working!")
print("=" * 70)
print()

try:
    # Run debug script
    result = subprocess.run([sys.executable, "debug_voice.py"], check=False)
    sys.exit(result.returncode)
except KeyboardInterrupt:
    print("\n\n⏹️  Debug tool stopped by user")
    sys.exit(0)
except Exception as e:
    print(f"\n❌ Error running debug tool: {e}")
    sys.exit(1)
