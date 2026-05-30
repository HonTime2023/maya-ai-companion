"""
Health Analysis Module — Voice-callable health tracking functions for JARVIS.
All functions return plain spoken strings (no markdown).
"""
from datetime import date
from health_memory import (
    load_profile, save_profile, update_field, append_to_log,
    get_log_entries, log_checkin,
    set_emergency_contact as _set_contact,
    reset_hydration_if_new_day,
)


def log_sleep(hours: float, quality: str = "fair") -> str:
    """Log tonight's sleep hours and optional quality (good/fair/poor)."""
    try:
        hours = float(hours)
    except (ValueError, TypeError):
        return "I did not catch how many hours you slept. Please say a number like 7 or 6.5."

    today = date.today().isoformat()
    append_to_log("sleep_log", {"date": today, "hours": hours, "quality": quality})
    log_checkin()

    # Recompute 7-day average
    recent = get_log_entries("sleep_log", days=7)
    if recent:
        avg = round(sum(e["hours"] for e in recent) / len(recent), 1)
        update_field("sleep_hours_avg", avg)
    else:
        avg = hours

    if hours < 6:
        return (
            f"Logged {hours} hours of sleep. That is below the recommended 7 to 8 hours. "
            f"Your 7-day average is now {avg} hours. Try to get to bed a little earlier tonight."
        )
    if hours < 7:
        return (
            f"Logged {hours} hours of sleep. You are almost there — aim for at least 7 for full recovery. "
            f"Average this week: {avg} hours."
        )
    return (
        f"Great! Logged {hours} hours of sleep. Your 7-day average is {avg} hours. Keep it up!"
    )


def log_water(glasses: int = 1) -> str:
    """Log glasses of water drunk today."""
    try:
        glasses = int(glasses)
    except (ValueError, TypeError):
        glasses = 1

    reset_hydration_if_new_day()
    profile = load_profile()
    profile["hydration_today"] = profile.get("hydration_today", 0) + glasses
    goal = profile.get("hydration_goal", 8)
    current = profile["hydration_today"]
    save_profile(profile)
    log_checkin()

    if current >= goal:
        return (
            f"You have hit your daily water goal of {goal} glasses! "
            f"You have had {current} glasses total today. Excellent hydration!"
        )
    remaining = goal - current
    return (
        f"Logged {glasses} glass{'es' if glasses > 1 else ''} of water. "
        f"You are at {current} out of {goal} today. {remaining} more to go!"
    )


def log_mood(mood: str, score: int = None) -> str:
    """Log current mood. Score is optional 1-10 (auto-inferred if not given)."""
    today = date.today().isoformat()

    mood_lower = mood.lower()
    if score is None:
        if any(w in mood_lower for w in ["great", "amazing", "excellent", "happy", "fantastic", "wonderful"]):
            score = 9
        elif any(w in mood_lower for w in ["good", "fine", "okay", "well", "alright"]):
            score = 7
        elif any(w in mood_lower for w in ["tired", "meh", "neutral", "so-so"]):
            score = 5
        elif any(w in mood_lower for w in ["stressed", "anxious", "worried", "nervous", "tense"]):
            score = 4
        elif any(w in mood_lower for w in ["sad", "low", "down", "depressed", "bad", "unhappy"]):
            score = 3
        elif any(w in mood_lower for w in ["terrible", "awful", "horrible", "overwhelmed", "miserable"]):
            score = 2
        else:
            score = 5

    append_to_log("mood_log", {"date": today, "mood": mood, "score": score})
    update_field("stress_level", "high" if score <= 4 else "moderate" if score <= 6 else "low")
    log_checkin()

    # Detect 3+ consecutive low-mood days
    recent = get_log_entries("mood_log", days=4)
    low_days = sum(1 for e in recent if e.get("score", 5) <= 4)
    if low_days >= 3:
        return (
            f"I have logged your mood as {mood}. I noticed you have been feeling low for a few days now. "
            f"I am here for you. Would you like to talk about it, or shall I play some calming music?"
        )

    if score >= 8:
        return f"That is wonderful! Logged your mood as {mood}. Keep that positive energy going!"
    if score >= 6:
        return f"Logged your mood as {mood}. Glad you are doing alright."
    if score <= 4:
        return (
            f"I am sorry you are feeling {mood}. I have noted that. "
            f"Be kind to yourself today and take it easy."
        )
    return f"Logged your mood as {mood}."


def log_symptom(symptom: str, severity: int = 5) -> str:
    """Log a health symptom with severity 1-10."""
    try:
        severity = max(1, min(10, int(severity)))
    except (ValueError, TypeError):
        severity = 5

    today = date.today().isoformat()
    append_to_log("symptom_log", {"date": today, "symptom": symptom.lower(), "severity": severity})
    log_checkin()

    # Repeated symptom check
    recent = get_log_entries("symptom_log", days=7)
    repeat_count = sum(1 for e in recent if symptom.lower() in e.get("symptom", "").lower())

    profile = load_profile()
    conditions = [c.lower() for c in profile.get("conditions", [])]

    parts = [f"Logged symptom: {symptom}, severity {severity} out of 10."]

    if severity >= 8:
        parts.append("That sounds quite severe. Please rest and consider contacting your doctor if it persists.")

    if repeat_count >= 3:
        parts.append(
            f"I have also noticed you have reported {symptom} {repeat_count} times this week. "
            f"It may be worth mentioning to your doctor."
        )

    if "diabetes" in conditions and any(w in symptom.lower() for w in ["dizzy", "dizziness", "shaky", "weak", "faint"]):
        parts.append("Since you have diabetes, dizziness can sometimes be linked to blood sugar levels. Have you eaten recently?")

    if "hypertension" in conditions and any(w in symptom.lower() for w in ["headache", "head", "dizzy", "blurred"]):
        parts.append("With your hypertension, headaches can sometimes signal elevated blood pressure. Try to rest and reduce stress.")

    return " ".join(parts)


def log_exercise(activity: str, duration_minutes: int) -> str:
    """Log a physical activity with duration in minutes."""
    try:
        duration_minutes = int(duration_minutes)
    except (ValueError, TypeError):
        return "I did not catch the duration. Please say something like '30 minutes of walking'."

    today = date.today().isoformat()
    append_to_log("exercise_log", {"date": today, "activity": activity, "duration_minutes": duration_minutes})
    log_checkin()

    week_log = get_log_entries("exercise_log", days=7)
    exercise_days = len(set(e["date"] for e in week_log))
    total_mins = sum(e.get("duration_minutes", 0) for e in week_log)

    encouragement = "Great workout!" if duration_minutes >= 30 else "Every bit of movement counts!"

    if exercise_days >= 5:
        return f"{encouragement} Logged {duration_minutes} minutes of {activity}. You have been active {exercise_days} days this week — outstanding!"
    if exercise_days >= 3:
        return f"{encouragement} Logged {duration_minutes} minutes of {activity}. That is {exercise_days} active days and {total_mins} total minutes this week. Keep going!"
    return f"{encouragement} Logged {duration_minutes} minutes of {activity}. You are building a great habit — {exercise_days} active day{'s' if exercise_days != 1 else ''} this week so far."


def log_medication_taken(name: str) -> str:
    """Confirm that a medication has been taken."""
    today = date.today().isoformat()
    append_to_log("medication_log", {"date": today, "name": name, "taken": True})
    log_checkin()
    return f"Marked {name} as taken for today. Well done for staying consistent with your medication."


def add_medication(name: str, dosage: str = "", times: str = "morning") -> str:
    """Add or update a medication in the health profile."""
    profile = load_profile()
    meds = profile.get("medications", [])

    for m in meds:
        if m.get("name", "").lower() == name.lower():
            m["dosage"] = dosage or m.get("dosage", "")
            m["times"] = times
            save_profile(profile)
            return f"Updated {name} in your medication list. Times: {times}."

    meds.append({"name": name, "dosage": dosage, "times": times})
    profile["medications"] = meds
    save_profile(profile)
    return f"Added {name} to your medication list. I will remind you to take it {times}."


def add_health_condition(condition: str) -> str:
    """Add a medical condition to the health profile."""
    profile = load_profile()
    conditions = profile.get("conditions", [])
    if condition.lower() not in [c.lower() for c in conditions]:
        conditions.append(condition)
        profile["conditions"] = conditions
        save_profile(profile)
        return (
            f"I have noted {condition} in your health profile. "
            f"I will keep this in mind when giving you health advice."
        )
    return f"{condition} is already in your health profile."


def set_health_emergency_contact(phone_number: str) -> str:
    """Set emergency contact phone number in international format."""
    return _set_contact(phone_number)


def get_health_summary() -> str:
    """Return a spoken health summary for today."""
    reset_hydration_if_new_day()
    profile = load_profile()
    parts = []

    sleep_avg = profile.get("sleep_hours_avg")
    if sleep_avg:
        parts.append(f"your 7-day sleep average is {sleep_avg} hours")

    hydration = profile.get("hydration_today", 0)
    goal = profile.get("hydration_goal", 8)
    parts.append(f"you have had {hydration} out of {goal} glasses of water today")

    recent_mood = get_log_entries("mood_log", days=1)
    if recent_mood:
        parts.append(f"your mood today is {recent_mood[-1].get('mood', 'not logged')}")

    week_exercise = get_log_entries("exercise_log", days=7)
    exercise_days = len(set(e["date"] for e in week_exercise))
    if exercise_days > 0:
        parts.append(f"you have exercised {exercise_days} day{'s' if exercise_days != 1 else ''} this week")

    meds = profile.get("medications", [])
    if meds:
        today = date.today().isoformat()
        taken_today = [e["name"] for e in profile.get("medication_log", [])
                       if e.get("date") == today and e.get("taken")]
        not_taken = [m["name"] for m in meds if m["name"] not in taken_today]
        if not_taken:
            parts.append(f"you still need to take {', '.join(not_taken)}")

    recent_symptoms = get_log_entries("symptom_log", days=1)
    if recent_symptoms:
        names = [e["symptom"] for e in recent_symptoms]
        parts.append(f"symptoms logged today: {', '.join(names)}")

    if not parts:
        return (
            "I do not have much health data logged yet. "
            "Try telling me how you slept, how much water you have had, or how you are feeling."
        )
    return "Here is your health summary. " + ". ".join(p.capitalize() for p in parts) + "."


def get_wellness_score() -> str:
    """Calculate and speak a wellness score out of 100."""
    reset_hydration_if_new_day()
    profile = load_profile()
    score = 0
    breakdown = []

    # Sleep — 30 pts
    sleep_log = get_log_entries("sleep_log", days=3)
    if sleep_log:
        avg = sum(e["hours"] for e in sleep_log) / len(sleep_log)
        pts = 30 if avg >= 8 else 25 if avg >= 7 else 15 if avg >= 6 else 5
        score += pts
        breakdown.append(f"sleep {pts} out of 30")

    # Hydration — 20 pts
    hydration = profile.get("hydration_today", 0)
    goal = profile.get("hydration_goal", 8)
    pts = min(20, int((hydration / max(goal, 1)) * 20))
    score += pts
    breakdown.append(f"hydration {pts} out of 20")

    # Mood — 20 pts
    mood_log = get_log_entries("mood_log", days=3)
    if mood_log:
        avg_m = sum(e.get("score", 5) for e in mood_log) / len(mood_log)
        pts = min(20, int((avg_m / 10) * 20))
        score += pts
        breakdown.append(f"mood {pts} out of 20")

    # Exercise — 20 pts
    week_ex = get_log_entries("exercise_log", days=7)
    ex_days = len(set(e["date"] for e in week_ex))
    pts = min(20, ex_days * 4)
    score += pts
    breakdown.append(f"exercise {pts} out of 20")

    # Medication adherence — 10 pts
    meds = profile.get("medications", [])
    if meds:
        med_log = get_log_entries("medication_log", days=7)
        taken = sum(1 for e in med_log if e.get("taken"))
        expected = len(meds) * 7
        pts = min(10, int((taken / max(expected, 1)) * 10))
    else:
        pts = 10
    score += pts
    breakdown.append(f"medication adherence {pts} out of 10")

    if score >= 85:
        verdict = "You are doing exceptionally well!"
    elif score >= 70:
        verdict = "You are in good shape overall. Keep it up."
    elif score >= 50:
        verdict = "There is room to improve. Focus on sleep and hydration."
    else:
        verdict = "Your wellness needs some attention. Let us work on it together."

    detail = ", ".join(breakdown)
    return f"Your wellness score today is {score} out of 100. {verdict} Breakdown: {detail}."
