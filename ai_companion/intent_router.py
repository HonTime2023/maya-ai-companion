import re


def detect_intent(text):
    text = text.lower()

    # Change name command
    if "change my name" in text or "my name is" in text.replace("is ", ""):
        return "change_name"

    if "time" in text:
        return "time"
    # play music (generic) - match "play (something) music"
    if re.search(r"\bplay\b.*\bmusic\b", text):
        return "play_music"
    
    # play song (specific song)
    if re.search(r"\bplay\b", text) and "music" not in text:
        return "play_song"

    # pause music
    if "pause" in text or "stop music" in text:
        return "pause_music"

    # resume music
    if "resume" in text or "continue music" in text:
        return "resume_music"

    # skip
    if "next song" in text or "skip" in text:
        return "next_track"
    # previous
    if "previous song" in text or "go back" in text:
        return "previous_track"

    if "date" in text:
        return "date"

    if "weather" in text:
        return "weather"

    # Check FIRST if user is checking/listing alarms (not setting)
    if "check alarm" in text or "show alarm" in text or "list alarm" in text or "my alarms" in text:
        return "check_alarm"

    # STRICT: Only set alarm if explicitly asking to SET/CREATE at specific time
    # More permissive patterns to catch variations like "set alarm", "wake me up", etc.
    if re.search(r'(?:set|create|make|add|wake).*?alarm', text, re.IGNORECASE) and \
       re.search(r'(?:for|at|at the)\s*\d', text, re.IGNORECASE):
        return "alarm"
    
    # Also catch "alarm me" or "alert me" patterns
    if re.search(r'(?:alarm|wake|remind).*?(?:for|at|at the)\s*\d', text, re.IGNORECASE) and \
       "check" not in text.lower():
        return "alarm"

    if "remind me" in text or "reminder" in text or "remind me to" in text:
        return "reminder"

    if "check remind" in text or "show remind" in text or "list remind" in text or "my reminders" in text:
        return "check_reminder"

    if "i'm in" in text or "i am in" in text or "located in" in text or "location" in text or "my location is" in text or "city is" in text or "from" in text:
        return "location"

    if "emergency contact" in text:
        return "emergency_contact"

    if "help me" in text or "emergency" in text:
        return "emergency"

    return None
