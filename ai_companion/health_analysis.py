import re
from health_memory import update_field


def extract_sleep_hours(text):
    # Try to find a number like 6 or 7.5
    match = re.search(r"(\d+(\.\d+)?)", text)

    if match:
        hours = float(match.group(1))
        update_field("sleep_hours_avg", hours)
        return f"Logged {hours} hours of sleep."

    return "I couldn't determine the number of hours slept."


def detect_stress(text):
    text = text.lower()

    if any(word in text for word in ["stressed", "overwhelmed", "anxious"]):
        update_field("stress_level", "high")
        return "I'm sorry you're feeling stressed. I've updated your stress level, and I'm here to help if you want to talk about it."

    if any(word in text for word in ["tired", "low energy"]):
        update_field("stress_level", "moderate")
        return "I've noted moderate fatigue. Make sure to take breaks and rest when you can."

    return None
