import json
import os
from datetime import datetime

FILE_NAME = "health_profile.json"

DEFAULT_PROFILE = {
    "name": "Naomi",
    "age": None,
    "conditions": [],
    "medications": [],
    "emergency_contact": None,
    "doctor_contact": None,
    "sleep_hours_avg": None,
    "stress_level": None,
    "last_check_in": None,
    "hydration_today": 0,
    "last_report_sent": None,
}


def mark_report_sent():
    profile = load_profile()
    profile["last_report_sent"] = datetime.now().isoformat()
    save_profile(profile)


def report_sent_today():
    profile = load_profile()
    last = profile.get("last_report_sent")

    if not last:
        return False

    last_time = datetime.fromisoformat(last)
    return datetime.now().date() == last_time.date()


def load_profile():
    if not os.path.exists(FILE_NAME):
        save_profile(DEFAULT_PROFILE)
        return DEFAULT_PROFILE
    with open(FILE_NAME, "r") as f:
        return json.load(f)


def save_profile(profile):
    with open(FILE_NAME, "w") as f:
        json.dump(profile, f, indent=4)


def update_field(key, value):
    profile = load_profile()
    profile[key] = value
    save_profile(profile)


def set_emergency_contact(number):
    profile = load_profile()

    if not number.startswith("+") or not number[1:].isdigit():
        return "Invalid number format. Use international format like +2348012345678."

    profile["emergency_contact"] = number
    save_profile(profile)

    return f"Emergency contact set to {number}."


def get_emergency_contact():
    profile = load_profile()
    return profile.get("emergency_contact")


def log_checkin():
    profile = load_profile()
    profile["last_check_in"] = datetime.now().isoformat()
    save_profile(profile)


def needs_daily_checkin():
    profile = load_profile()
    last = profile.get("last_check_in")

    if not last:
        return True

    last_time = datetime.fromisoformat(last)
    return datetime.now().date() != last_time.date()
