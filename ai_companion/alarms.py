"""
Alarms: User-specific alarm management with proper time handling.
"""

import json
from datetime import datetime
from user_manager import get_current_user


def load_alarms():
    """Load alarms for current user."""
    user = get_current_user()
    return user.get_alarms()


def save_alarms(alarms):
    """Save alarms for current user."""
    user = get_current_user()
    user.save_alarms(alarms)


def add_alarm(time_str: str, note: str):
    """
    Add an alarm.
    
    Args:
        time_str: Time in format "HH:MM" (24-hour format)
        note: Alarm description
    """
    if not time_str or not note:
        print("❌ Invalid alarm data")
        return False

    # Normalize time to HH:MM
    time_str = _normalize_time(time_str)
    if not time_str:
        print("❌ Invalid time format")
        return False

    alarms = load_alarms()
    alarms.append({
        "time": time_str,
        "note": note,
        "last_triggered": None,
        "enabled": True,
        "created_at": datetime.now().isoformat()
    })

    save_alarms(alarms)
    print(f"✅ Alarm set: {note} at {time_str}")
    return True


def check_alarms():
    """
    Check for alarms that are due.
    Returns list of alarm notes that are due.
    """
    alarms = load_alarms()
    now = datetime.now().strftime("%H:%M")
    triggered = []

    for alarm in alarms:
        if not alarm.get("enabled", True):
            continue

        raw_time = alarm.get("time", "").strip()

        # Normalize stored time to HH:MM
        normalized = _normalize_time(raw_time)
        if not normalized:
            continue

        # Check if time matches and hasn't been triggered in this minute
        if normalized == now and alarm.get("last_triggered") != now:
            alarm["last_triggered"] = now
            alarm["time"] = normalized  # Fix the stored value going forward
            label = alarm.get("note") or alarm.get("description") or "Alarm"
            triggered.append(label)

    save_alarms(alarms)
    return triggered


def delete_alarm(index: int):
    """Delete a specific alarm."""
    alarms = load_alarms()
    if 0 <= index < len(alarms):
        del alarms[index]
        save_alarms(alarms)
        return True
    return False


def disable_alarm(index: int):
    """Disable an alarm without deleting it."""
    alarms = load_alarms()
    if 0 <= index < len(alarms):
        alarms[index]["enabled"] = False
        save_alarms(alarms)
        return True
    return False


def list_alarms():
    """List all alarms for current user."""
    alarms = load_alarms()
    return alarms


def _normalize_time(time_str: str) -> str:
    """
    Normalize time string to HH:MM (24-hour) format.
    Handles: "9", "9:00", "09:00", "9 am", "9am", "9:00 AM", "9:30 PM",
             "at 9 AM", "for 7:30 PM", etc.
    """
    import re as _re
    if not time_str:
        return None

    s = time_str.lower().strip()
    # Strip leading "at the", "at", "for" prefixes
    s = _re.sub(r'^(?:at\s+the\s+|at\s+|for\s+)', '', s).strip()
    # Normalise a.m./p.m.
    s = s.replace("a.m.", "am").replace("p.m.", "pm")

    # Detect and strip AM/PM suffix BEFORE splitting on ":"
    is_pm = s.endswith("pm") or " pm" in s
    is_am = s.endswith("am") or " am" in s
    s = _re.sub(r'\s*(am|pm)\s*$', '', s).strip()

    try:
        if ":" in s:
            parts = s.split(":")
            hour = int(parts[0].strip())
            minute = int(parts[1].strip()) if len(parts) > 1 else 0
        else:
            hour = int(s.strip())
            minute = 0

        # Apply 12-hour → 24-hour conversion
        if is_pm and hour != 12:
            hour += 12
        elif is_am and hour == 12:
            hour = 0

        if not (0 <= hour <= 23) or not (0 <= minute <= 59):
            return None

        return f"{hour:02d}:{minute:02d}"

    except (ValueError, IndexError):
        return None
