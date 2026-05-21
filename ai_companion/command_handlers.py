"""
Command Handlers: Execute actual commands (time, weather, alarms, reminders)
These are called BEFORE sending to LLM to provide real data
"""

from datetime import datetime
from user_manager import get_current_user
import re
from weather import get_weather

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger("Commands")


def handle_time_command(text: str) -> str:
    """Handle 'what time is it' requests"""
    current_time = datetime.now().strftime("%I:%M %p")
    return f"The current time is {current_time}."


def handle_date_command(text: str) -> str:
    """Handle 'what date is it' requests"""
    current_date = datetime.now().strftime("%A, %B %d, %Y")
    return f"Today is {current_date}."


def handle_weather_command(text: str) -> str:
    """Handle weather requests - get location from user profile and fetch real weather"""
    try:
        user = get_current_user()
        location = user.data.get("location", None)
        
        if not location or location.lower() in ["unknown", "not set"]:
            return "I don't know your location yet. Could you tell me what city or area you're in? Then I can help with weather!"
        
        # Get real-time weather from OpenWeather API
        logger.info(f"[COMMAND] Weather request for {location}")
        weather_info = get_weather(location)
        return weather_info
    except Exception as e:
        logger.error(f"Weather command error: {e}")
        return "I couldn't fetch the weather right now. Could you tell me your location?"


def handle_check_alarms(text: str) -> str:
    """Check user's alarms"""
    try:
        user = get_current_user()
        alarms = user.get_alarms()
        
        if not alarms:
            return "You don't have any alarms set."
        
        response = "Your alarms are:\n"
        for alarm in alarms:
            response += f"- {alarm.get('description', 'Alarm')} at {alarm.get('time', 'unknown time')}\n"
        return response.strip()
    except Exception as e:
        logger.error(f"Error checking alarms: {e}")
        return "I couldn't retrieve your alarms."


def handle_set_alarm(text: str) -> str:
    """Set a new alarm - MUST have explicit action words"""
    try:
        # STRICT: Only match if we can find BOTH an action word AND a time
        # Patterns: "set alarm for 7 AM", "wake me at 6:30 AM", etc.
        action_words = r'(?:set|create|make|add|wake)\s+(?:an?\s+)?alarm|(?:wake|alarm)\s+me'
        
        if not re.search(action_words, text, re.IGNORECASE):
            return None  # No alarm action word found
        
        # Extract the time
        time_match = re.search(r'(?:for|at|at the)\s+(\d{1,2})(?:[:.]?(\d{2}))?\s*(am|pm|AM|PM|a\.m\.|p\.m\.)', text, re.IGNORECASE)
        
        if not time_match:
            return "Could you tell me what time you want to set the alarm for? For example: 7 AM or 2:30 PM"
        
        time_str = time_match.group(0).strip()
        time_str = re.sub(r'a\.m\.', 'AM', time_str, flags=re.IGNORECASE)
        time_str = re.sub(r'p\.m\.', 'PM', time_str, flags=re.IGNORECASE)
        
        # Extract description (what the alarm is for)
        description = "Alarm"
        if "wake" in text.lower():
            description = "Wake up alarm"
        else:
            # Check if there's a specific purpose mentioned
            for_match = re.search(r'(?:to|for)\s+([a-z\s]+?)(?:at|for the)', text, re.IGNORECASE)
            if for_match:
                desc_text = for_match.group(1).strip()
                if desc_text and len(desc_text) < 30 and desc_text not in ['an alarm', 'alarm', 'me']:
                    description = desc_text.capitalize()
        
        user = get_current_user()
        alarm_data = {
            'time': time_str,
            'description': description,
            'enabled': True,
            'created_at': datetime.now().isoformat()
        }
        user.add_alarm(alarm_data)
        logger.info(f"[ALARM SET] Successfully set: {description} at {time_str}")
        return f"Got it! I've set your alarm for {time_str}. {description}."
    except Exception as e:
        logger.error(f"Error setting alarm: {e}")
        return None


def handle_check_reminders(text: str) -> str:
    """Check user's reminders"""
    try:
        user = get_current_user()
        reminders = user.get_reminders()
        
        if not reminders:
            return "You don't have any reminders set."
        
        response = "Your reminders are:\n"
        for reminder in reminders:
            response += f"- {reminder.get('description', 'Reminder')} at {reminder.get('time', 'unknown time')}\n"
        return response.strip()
    except Exception as e:
        logger.error(f"Error checking reminders: {e}")
        return "I couldn't retrieve your reminders."


def handle_set_reminder(text: str) -> str:
    """Set a new reminder - MUST have explicit action words"""
    try:
        # STRICT: Only match if "remind me" is in the text (not just casual mentions)
        if "remind me" not in text.lower():
            return None  # Not a reminder request
        
        # Extract time - supports various formats like "at 3 PM", "in 2 hours", "for tomorrow"
        time_match = re.search(r'(?:at|for|in)\s+(\d{1,2})(?:[:.]?(\d{2}))?\s*(am|pm|AM|PM|a\.m\.|p\.m\.)', text, re.IGNORECASE)
        
        if not time_match:
            return "When would you like to be reminded? (e.g., at 3 PM or in 2 hours)"
        
        time_str = time_match.group(0).strip()
        time_str = re.sub(r'a\.m\.', 'AM', time_str, flags=re.IGNORECASE)
        time_str = re.sub(r'p\.m\.', 'PM', time_str, flags=re.IGNORECASE)
        
        # Extract what to remind about (text between "remind me" and the time)
        description_match = re.search(r'remind me\s+(?:to\s+)?(.+?)(?:\s+(?:at|for|in)\s+\d|$)', text, re.IGNORECASE)
        description = "Reminder"
        if description_match:
            desc_candidate = description_match.group(1).strip()
            if desc_candidate and len(desc_candidate) < 50 and desc_candidate.lower() not in ["reminder", "something", "to"]:
                description = desc_candidate
        
        user = get_current_user()
        user.add_reminder({
            'time': time_str,
            'description': description,
            'created_at': datetime.now().isoformat()
        })
        
        logger.info(f"[REMINDER SET] {description} at {time_str}")
        return f"Got it! I'll remind you to {description} at {time_str}."
    except Exception as e:
        logger.error(f"Error setting reminder: {e}")
        return None


def handle_location_command(text: str) -> str:
    """Extract and save user's location."""
    try:
        # Extract location from common patterns
        location_match = re.search(r"(?:i'm|i am|located|in|from)\s+(?:in\s+)?([A-Za-z\s]+?)(?:and|\.|,|$)", text, re.IGNORECASE)
        
        if location_match:
            location = location_match.group(1).strip()
            # Clean up the location string
            location = re.sub(r'\b(and|in|from|located)\b', '', location, flags=re.IGNORECASE).strip()
            
            if location and len(location) < 50:  # Sanity check
                user = get_current_user()
                user.set_location(location)
                logger.info(f"[LOCATION] Set user location to: {location}")
                return f"Got it! I've saved that you're in {location}. Now I can help with location-specific info!"
        
        return "Could you tell me what city or area you're in?"
    except Exception as e:
        logger.error(f"Location command error: {e}")
        return "I couldn't parse your location. Could you tell me your city?"


def handle_set_name(name: str) -> str:
    """Save the user's name to their profile."""
    try:
        name = name.strip().title()
        user = get_current_user()
        user.update_name(name)
        logger.info(f"[NAME] Set user name to: {name}")
        return f"Got it! I'll call you {name} from now on."
    except Exception as e:
        logger.error(f"Set name error: {e}")
        return "I had trouble saving your name, but I'll remember it for this session."


def handle_set_location(city: str) -> str:
    """Save the user's city/location to their profile."""
    try:
        city = city.strip().title()
        user = get_current_user()
        user.data["location"] = city
        user.save_profile()
        logger.info(f"[LOCATION] Set user location to: {city}")
        return f"Got it! I've saved that you're in {city}. I can now fetch weather for you there."
    except Exception as e:
        logger.error(f"Set location error: {e}")
        return "I had trouble saving your location."


def handle_command(intent: str, text: str) -> tuple:
    """
    Handle a command and return (response, should_skip_llm)
    If should_skip_llm is True, don't send to LLM
    """
    
    if intent == "time":
        return handle_time_command(text), True
    elif intent == "date":
        return handle_date_command(text), True
    elif intent == "weather":
        return handle_weather_command(text), True
    elif intent == "location":
        return handle_location_command(text), True
    elif intent == "check_alarm":
        return handle_check_alarms(text), True
    elif intent == "alarm":
        return handle_set_alarm(text), False  # May need LLM for clarification
    elif intent == "check_reminder":
        return handle_check_reminders(text), True
    elif intent == "reminder":
        return handle_set_reminder(text), False  # May need LLM for clarification
    
    return None, False
