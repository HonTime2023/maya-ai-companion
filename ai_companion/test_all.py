"""
Test Script: Verify all AI Companion components work correctly.
Runs comprehensive checks without requiring user input or hardware.
"""

import sys
import json
from pathlib import Path

def test_imports():
    """Test that all required modules can be imported."""
    print("\n🔍 Testing imports...")
    try:
        import user_manager
        import conversation
        import brain
        import reminders
        import alarms
        import intent_handlers
        import reminder_parser
        import alarm_parser
        import intent_router
        # Spotify is optional
        print("✅ All core imports successful")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False


def test_user_manager():
    """Test user manager functionality."""
    print("\n🔍 Testing user manager...")
    try:
        from user_manager import UserManager, get_current_user, get_current_user_name
        
        # Test getting current user
        user = get_current_user()
        name = get_current_user_name()
        
        assert user is not None, "User is None"
        assert name is not None, "User name is None"
        
        # Test user profile structure
        assert user.data.get("user_id") == "default_user"
        assert user.data.get("preferences") is not None
        assert user.data.get("health") is not None
        
        print(f"✅ User Manager working (User: {name})")
        return True
    except Exception as e:
        print(f"❌ User Manager test failed: {e}")
        return False


def test_conversation_system():
    """Test conversation history management."""
    print("\n🔍 Testing conversation system...")
    try:
        from conversation import (
            get_conversation_history,
            add_user_message,
            add_ai_message,
            build_system_prompt,
            clear_conversation_history
        )
        
        # Clear first
        clear_conversation_history()
        
        # Get initial history (should have system prompt)
        history = get_conversation_history()
        assert len(history) >= 1, "History should have at least system prompt"
        assert history[0]["role"] == "system", "First message should be system"
        
        # Test system prompt contains user name
        system_msg = history[0]["content"]
        assert "Default User" in system_msg or "default user" in system_msg.lower(), "System prompt should mention user"
        
        # Add messages
        add_user_message("Hello")
        add_ai_message("Hi there!")
        
        history = get_conversation_history()
        assert len(history) >= 3, "History should have system + user + ai"
        
        print("✅ Conversation system working")
        return True
    except Exception as e:
        print(f"❌ Conversation test failed: {e}")
        return False


def test_reminder_parsing():
    """Test reminder parsing."""
    print("\n🔍 Testing reminder parsing...")
    try:
        from reminder_parser import parse_reminder
        
        test_cases = [
            ("remind me to take medicine in 10 minutes", True),
            ("set a reminder tomorrow at 9am to call mom", True),
            ("remind me at 3:30pm to check the oven", True),
            ("just random text", False),
        ]
        
        for text, should_parse in test_cases:
            result = parse_reminder(text)
            if should_parse:
                assert result is not None, f"Should parse: {text}"
                task, time_str = result
                assert task is not None and len(task) > 0
                assert time_str is not None and ":" in time_str
            else:
                assert result is None, f"Should not parse: {text}"
        
        print("✅ Reminder parsing working")
        return True
    except Exception as e:
        print(f"❌ Reminder parsing test failed: {e}")
        return False


def test_intent_detection():
    """Test intent detection."""
    print("\n🔍 Testing intent detection...")
    try:
        from intent_router import detect_intent
        
        test_cases = {
            "what's the weather": "weather",
            "play some music": "play_music",
            "play music": "play_music",
            "play me some music": "play_music",
            "remind me to take medicine": "reminder",
            "what time is it": "time",
            "just random chat": None,
        }
        
        for text, expected_intent in test_cases.items():
            detected = detect_intent(text)
            assert detected == expected_intent, f"Expected {expected_intent}, got {detected} for '{text}'"
        
        print("✅ Intent detection working")
        return True
    except Exception as e:
        print(f"❌ Intent detection test failed: {e}")
        return False


def test_reminders_system():
    """Test reminders storage and checking."""
    print("\n🔍 Testing reminders system...")
    try:
        from reminders import add_reminder, check_reminders, list_reminders
        from datetime import datetime, timedelta
        
        # Set up a reminder for 1 minute from now
        now = datetime.now()
        past_time = (now - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M")
        
        # Add a reminder that should be due
        success = add_reminder(past_time, "Test task")
        assert success, "Should add reminder successfully"
        
        # Check reminders
        due = check_reminders()
        assert len(due) > 0, "Should have due reminders"
        assert "Test task" in due, "Our task should be due"
        
        print("✅ Reminders system working")
        return True
    except Exception as e:
        print(f"❌ Reminders system test failed: {e}")
        return False


def test_alarms_system():
    """Test alarms storage and checking."""
    print("\n🔍 Testing alarms system...")
    try:
        from alarms import add_alarm, check_alarms, list_alarms, _normalize_time
        from datetime import datetime
        
        # Test time normalization
        assert _normalize_time("9") == "09:00"
        assert _normalize_time("9:30") == "09:30"
        assert _normalize_time("9am") == "09:00"
        assert _normalize_time("9pm") == "21:00"
        assert _normalize_time("21:00") == "21:00"
        
        # Add an alarm
        success = add_alarm("14:30", "Test alarm")
        assert success, "Should add alarm successfully"
        
        # List alarms
        alarms = list_alarms()
        assert len(alarms) > 0, "Should have alarms"
        
        print("✅ Alarms system working")
        return True
    except Exception as e:
        print(f"❌ Alarms system test failed: {e}")
        return False


def test_intent_handlers():
    """Test intent handler responses."""
    print("\n🔍 Testing intent handlers...")
    try:
        from intent_handlers import handle_intent
        from user_manager import get_current_user_name
        
        user_name = get_current_user_name()
        
        # Test various intents (skip Spotify-dependent ones if not available)
        response = handle_intent("time", "what time is it")
        assert response is not None, "Should return time"
        assert ":" in response, "Should contain time"
        
        response = handle_intent("date", "what's today")
        assert response is not None, "Should return date"
        
        # Weather might not work without API setup, but handler should exist
        # Skip asserting response content for optional APIs
        
        print("✅ Intent handlers working")
        return True
    except Exception as e:
        print(f"❌ Intent handlers test failed: {e}")
        return False


def test_api_models():
    """Test that API model names are correct."""
    print("\n🔍 Testing API model names...")
    try:
        # Read source files directly with UTF-8 encoding
        with open("stt_openai.py", "r", encoding="utf-8") as f:
            stt_source = f.read()
        assert 'model="whisper-1"' in stt_source, "STT should use whisper-1 model"
        assert 'gpt-4o-mini-transcribe' not in stt_source, "STT should NOT use gpt-4o-mini-transcribe"
        
        with open("tts_openai.py", "r", encoding="utf-8") as f:
            tts_source = f.read()
        assert 'model="tts-1"' in tts_source, "TTS should use tts-1 model"
        assert 'gpt-4o-mini-tts' not in tts_source, "TTS should NOT use gpt-4o-mini-tts"
        
        print("✅ API model names correct")
        return True
    except Exception as e:
        print(f"❌ API model test failed: {e}")
        return False


def test_file_structure():
    """Test that user data directory structure is created."""
    print("\n🔍 Testing file structure...")
    try:
        users_dir = Path("users/default_user")
        assert users_dir.exists(), "Users directory should exist"
        
        profile_file = users_dir / "profile.json"
        assert profile_file.exists(), "Profile file should exist"
        
        # Verify profile JSON is valid
        with open(profile_file) as f:
            profile = json.load(f)
        
        assert profile["user_id"] == "default_user"
        assert "name" in profile
        assert "preferences" in profile
        
        print("✅ File structure correct")
        return True
    except Exception as e:
        print(f"❌ File structure test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("🤖 AI COMPANION - COMPONENT VERIFICATION")
    print("=" * 60)
    
    tests = [
        ("Imports", test_imports),
        ("User Manager", test_user_manager),
        ("Conversation System", test_conversation_system),
        ("Reminder Parsing", test_reminder_parsing),
        ("Intent Detection", test_intent_detection),
        ("Reminders System", test_reminders_system),
        ("Alarms System", test_alarms_system),
        ("Intent Handlers", test_intent_handlers),
        ("API Models", test_api_models),
        ("File Structure", test_file_structure),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:8} {test_name}")
    
    print("=" * 60)
    print(f"Result: {passed}/{total} tests passed")
    print("=" * 60)
    
    if passed == total:
        print("\n🎉 All tests passed! App is ready to run.")
        print("\n📝 To start the app:")
        print("   python main.py")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
