"""
Health Report Module — Generates weekly spoken health summaries for MAYA.
"""
from datetime import date
from health_memory import load_profile, get_log_entries


def generate_weekly_report() -> str:
    """Generate a full spoken weekly health report."""
    profile = load_profile()
    name = profile.get("name", "")
    name_part = f", {name}" if name and name.lower() not in ("user", "") else ""

    parts = [f"Here is your weekly health report{name_part}."]

    # --- Sleep ---
    sleep_log = get_log_entries("sleep_log", days=7)
    if sleep_log:
        avg = round(sum(e["hours"] for e in sleep_log) / len(sleep_log), 1)
        nights = len(sleep_log)
        parts.append(
            f"Sleep: you logged {nights} night{'s' if nights != 1 else ''} "
            f"with an average of {avg} hours."
        )
        if avg < 6:
            parts.append("That is below the healthy range — prioritizing rest could make a big difference.")
        elif avg >= 8:
            parts.append("Excellent sleep this week!")
    else:
        parts.append("Sleep was not logged this week. Try telling me how you slept each morning.")

    # --- Hydration ---
    hydration_log = get_log_entries("hydration_log", days=7)
    goal = profile.get("hydration_goal", 8)
    if hydration_log:
        days_hit = sum(1 for e in hydration_log if e.get("glasses", 0) >= goal)
        total_days = len(hydration_log)
        parts.append(
            f"Hydration: you hit your daily water goal {days_hit} out of {total_days} days."
        )
        if days_hit < total_days // 2:
            parts.append("Try to drink more water — even small sips throughout the day help.")
    else:
        parts.append("Hydration was not logged this week.")

    # --- Mood ---
    mood_log = get_log_entries("mood_log", days=7)
    if mood_log:
        avg_score = sum(e.get("score", 5) for e in mood_log) / len(mood_log)
        if avg_score >= 7:
            mood_desc = "mostly positive"
        elif avg_score >= 5:
            mood_desc = "mixed"
        else:
            mood_desc = "mostly low"
        parts.append(f"Mood: your mood this week was {mood_desc}.")
        if avg_score < 5:
            parts.append("If you have been feeling consistently low, please reach out to someone you trust.")
    else:
        parts.append("Mood was not logged this week.")

    # --- Exercise ---
    exercise_log = get_log_entries("exercise_log", days=7)
    if exercise_log:
        ex_days = len(set(e["date"] for e in exercise_log))
        total_mins = sum(e.get("duration_minutes", 0) for e in exercise_log)
        parts.append(
            f"Exercise: you were active {ex_days} day{'s' if ex_days != 1 else ''} "
            f"for a total of {total_mins} minutes."
        )
        if ex_days >= 5:
            parts.append("Outstanding activity level this week!")
    else:
        parts.append("No exercise was logged this week. Even a short walk makes a difference.")

    # --- Symptoms ---
    symptom_log = get_log_entries("symptom_log", days=7)
    if symptom_log:
        unique = list(set(e["symptom"] for e in symptom_log))
        parts.append(f"Symptoms logged this week: {', '.join(unique)}.")
        if len(symptom_log) >= 5:
            parts.append(
                "You logged quite a few symptoms this week. "
                "Consider scheduling a check-up with your doctor."
            )

    # --- Medication ---
    meds = profile.get("medications", [])
    if meds:
        med_log = get_log_entries("medication_log", days=7)
        taken = sum(1 for e in med_log if e.get("taken"))
        expected = len(meds) * 7
        pct = int((taken / max(expected, 1)) * 100)
        parts.append(f"Medication adherence: {pct} percent this week.")
        if pct < 80:
            parts.append("Try to be more consistent — your medications work best when taken regularly.")
        elif pct == 100:
            parts.append("Perfect medication adherence — excellent discipline!")

    parts.append("That is the end of your weekly report. Keep taking great care of yourself!")
    return " ".join(parts)
