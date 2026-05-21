"""
Intent Handlers: Route and handle user intents with personalized responses.
Removes hardcoded templates in favor of dynamic, context-aware responses.
"""

from datetime import datetime
from weather import get_weather
from reminders import add_reminder
from alarms import add_alarm
from reminder_parser import parse_reminder
from alarm_parser import parse_alarm
from emergency import trigger_emergency
from health_memory import set_emergency_contact
from spotify_service import (
    play_song,
    play_music,
    pause_music,
    resume_music,
    next_track,
    previous_track,
)
from user_manager import get_current_user_name
import random


def _get_user_name() -> str:
    """Get current user's name for personalization."""
    return get_current_user_name()


def _affirm(user_name: str = None) -> str:
    """Generate natural affirmation response."""
    if user_name is None:
        user_name = _get_user_name()
    
    affirmations = [
        f"Got it, {user_name}.",
        f"Done, {user_name}.",
        f"Perfect, {user_name}.",
        f"All set, {user_name}.",
        "Done.",
        "Got it.",
        "Sure thing.",
        "No problem.",
    ]
    return random.choice(affirmations)


def handle_intent(intent: str, text: str) -> str:
    """
    Route and handle detected intents with natural, personalized responses.
    
    Args:
        intent: Type of intent detected
        text: Original user input
        
    Returns:
        Response string or None if intent couldn't be handled
    """
    
    user_name = _get_user_name()

    # ====== MUSIC CONTROLS ======
    if intent == "play_music":
        try:
            play_music()
            responses = [
                "Now playing some great music for you.",
                "Let's get some music going.",
                "Putting on some music.",
                "Music time!",
            ]
            return random.choice(responses)
        except Exception as e:
            print(f"⚠️ Music error: {e}")
            return "I'm having trouble with the music. Is Spotify connected?"

    if intent == "play_song":
        try:
            query = text.replace("play", "").strip()
            play_song(query)
            responses = [
                f"Now playing {query}.",
                f"Putting on {query}.",
                f"Playing {query} for you.",
            ]
            return random.choice(responses)
        except Exception as e:
            print(f"⚠️ Music error: {e}")
            return f"I couldn't play {query}. Can you check if Spotify is set up?"

    if intent == "pause_music":
        try:
            pause_music()
            responses = ["Pausing the music.", "Music paused.", "Taking a break."]
            return random.choice(responses)
        except Exception as e:
            return "I couldn't pause the music."

    if intent == "resume_music":
        try:
            resume_music()
            responses = ["Resuming.", "Music's back on.", "Let's get back to it."]
            return random.choice(responses)
        except Exception as e:
            return "I couldn't resume the music."

    if intent == "next_track":
        try:
            next_track()
            responses = ["Next track.", "Skipping to the next one.", "Moving on."]
            return random.choice(responses)
        except Exception as e:
            return "I couldn't skip to the next track."

    if intent == "previous_track":
        try:
            previous_track()
            responses = ["Going back.", "Playing the previous track.", "Back we go."]
            return random.choice(responses)
        except Exception as e:
            return "I couldn't go back."

    # ====== ALARMS ======
    if intent == "alarm":
        alarm = parse_alarm(text)

        if not alarm:
            return f"I didn't catch the alarm time, {user_name}. Can you say it again?"

        time_str, note = alarm
        
        if add_alarm(time_str, note):
            responses = [
                f"Alarm set for {time_str}. I'll wake you up for {note}.",
                f"Got it. I'll alarm you at {time_str} to {note}.",
                f"Setting an alarm at {time_str} for {note}.",
            ]
            return random.choice(responses)
        else:
            return "I had trouble setting that alarm. Can you try again?"

    # ====== REMINDERS ======
    if intent == "reminder":
        reminder = parse_reminder(text)
        
        if not reminder:
            return f"I'm not sure when you want the reminder, {user_name}. Try saying something like 'remind me in 10 minutes to take my medicine.'"

        task, time_str = reminder
        
        if add_reminder(time_str, task):
            responses = [
                f"Reminder set, {user_name}. I'll remind you to {task} at {time_str}.",
                f"Got it. You'll hear from me about {task} at {time_str}.",
                f"I'll make sure to remind you to {task} at {time_str}.",
                f"Reminder added: {task} at {time_str}.",
            ]
            return random.choice(responses)
        else:
            return "I had trouble saving that reminder. Can you try again?"

    # ====== WEATHER ======
    if intent == "weather":
        try:
            # TODO: Get user's location from preferences instead of hardcoding
            weather_response = get_weather("Lagos")
            return weather_response
        except Exception as e:
            print(f"⚠️ Weather error: {e}")
            return "I'm having trouble getting the weather right now."

    # ====== TIME & DATE ======
    if intent == "time":
        now = datetime.now()
        time_str = now.strftime("%I:%M %p")
        responses = [
            f"It's {time_str}.",
            f"The time is {time_str}.",
            f"Right now it's {time_str}.",
        ]
        return random.choice(responses)

    if intent == "date":
        now = datetime.now()
        date_str = now.strftime("%A, %B %d, %Y")
        responses = [
            f"Today is {date_str}.",
            f"It's {date_str}.",
        ]
        return random.choice(responses)

    # ====== EMERGENCY ======
    if intent == "emergency":
        return trigger_emergency()

    return None
