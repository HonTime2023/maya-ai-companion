"""
Reminders: User-specific reminder management with proper time handling.
"""

import json
from datetime import datetime
from user_manager import get_current_user


def load_reminders():
    """Load reminders for current user."""
    user = get_current_user()
    return user.get_reminders()


def save_reminders(reminders):
    """Save reminders for current user."""
    user = get_current_user()
    user.save_reminders(reminders)


def add_reminder(time_str: str, message: str):
    """
    Add a reminder with proper validation.
    
    Args:
        time_str: Time in format "YYYY-MM-DD HH:MM" (already formatted by parser)
        message: Reminder task description
    """
    if not time_str or not message:
        print("❌ Invalid reminder data")
        return False

    reminders = load_reminders()
    
    try:
        # Validate time format
        datetime.strptime(time_str, "%Y-%m-%d %H:%M")
    except ValueError as e:
        print(f"❌ Invalid time format: {e}")
        return False

    reminders.append({
        "datetime": time_str,
        "message": message,
        "done": False,
        "created_at": datetime.now().isoformat()
    })

    save_reminders(reminders)
    print(f"✅ Reminder set: {message} at {time_str}")
    return True


def check_reminders():
    """
    Check for reminders that are due.
    Returns list of reminder messages that are due.
    """
    reminders = load_reminders()
    now = datetime.now()
    due = []

    for r in reminders:
        if r.get("done"):
            continue

        try:
            # Handle new format
            if "datetime" in r:
                reminder_time = datetime.strptime(r["datetime"], "%Y-%m-%d %H:%M")
            # Handle old format for migration
            elif "time" in r:
                today = now.strftime("%Y-%m-%d")
                reminder_time = datetime.strptime(
                    f"{today} {r['time']}", "%Y-%m-%d %H:%M"
                )
            else:
                continue

            if reminder_time <= now:
                due.append(r.get("message", "Reminder"))
                r["done"] = True

        except Exception as e:
            print(f"⚠️ Error checking reminder: {e}")

    # Save updated reminders
    if any(not r.get("done") for r in reminders):
        save_reminders(reminders)

    return due


def delete_reminder(index: int):
    """Delete a specific reminder."""
    reminders = load_reminders()
    if 0 <= index < len(reminders):
        del reminders[index]
        save_reminders(reminders)
        return True
    return False


def list_reminders():
    """List all pending reminders for current user."""
    reminders = load_reminders()
    pending = [r for r in reminders if not r.get("done")]
    return pending
