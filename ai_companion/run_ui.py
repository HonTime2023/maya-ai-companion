#!/usr/bin/env python3
"""
Launcher for AI Companion UI.
Starts the text-based GUI interface.
"""

import sys
import os
from pathlib import Path

# Ensure we're in the right directory
app_dir = Path(__file__).parent
os.chdir(app_dir)

# Check for .env file
if not Path(".env").exists():
    print("❌ ERROR: .env file not found!")
    print("Please create a .env file with your OpenAI API key and other credentials.")
    print("\nExpected contents:")
    print("OPENAI_API_KEY=your_key_here")
    print("TELEGRAM_BOT_TOKEN=your_token_here (optional)")
    print("TELEGRAM_CHAT_ID=your_chat_id_here (optional)")
    print("WEATHER_API_KEY=your_weather_key_here (optional)")
    print("SPOTIFY_CLIENT_ID=your_spotify_id_here (optional)")
    print("SPOTIFY_CLIENT_SECRET=your_spotify_secret_here (optional)")
    sys.exit(1)

# Check for required modules
required_modules = ["dotenv", "tkinter"]
missing = []
for module in required_modules:
    try:
        __import__(module)
    except ImportError:
        missing.append(module)

if missing:
    print(f"❌ ERROR: Missing required modules: {', '.join(missing)}")
    print(f"Please install with: pip install {' '.join(missing)}")
    sys.exit(1)

print("🚀 Launching AI Companion UI...")
print("=" * 50)

try:
    from ui import launch_ui
    launch_ui()
except Exception as e:
    print(f"❌ Failed to launch UI: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
