import re
from datetime import datetime, timedelta


def parse_reminder(text):

    text = text.lower().strip()

    if not any(word in text for word in ["remind", "reminder"]):
        return None

    now = datetime.now()

    target_time = None

    # ---------- "in X minutes / hours" / "in an hour" / "in half an hour" ----------
    # normalise word-numbers before matching digits
    text = re.sub(r"\bin a(n)?\b", "in 1", text)          # "in an hour" → "in 1 hour"
    text = re.sub(r"\bhalf an hour\b", "30 minutes", text)  # "in half an hour" → "in 30 minutes"
    text = re.sub(r"\ba (minute|min)\b", "1 \\1", text)    # "in a minute" → "in 1 minute"

    match = re.search(r"in (\d+) (minute|minutes|min|mins)", text)
    if match:
        mins = int(match.group(1))
        target_time = now + timedelta(minutes=mins)

    match = re.search(r"in (\d+) (hour|hours)", text)
    if match:
        hrs = int(match.group(1))
        target_time = now + timedelta(hours=hrs)

    # ---------- explicit time formats ----------
    if target_time is None:

        time_match = re.search(r"\b(\d{1,2})(:\d{2})?\s*(am|pm)?\b", text)

        if time_match:

            hour = int(time_match.group(1))
            minute = 0

            if time_match.group(2):
                minute = int(time_match.group(2)[1:])

            meridian = time_match.group(3)

            # convert am/pm
            if meridian == "pm" and hour != 12:
                hour += 12
            if meridian == "am" and hour == 12:
                hour = 0

            # detect 24h times like 18:30
            if hour > 23:
                hour = hour % 24

            target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # ---------- tomorrow ----------
    if target_time is None and "tomorrow" in text:

        target_time = (now + timedelta(days=1)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )

    # ---------- weekday ----------
    weekdays = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }

    if target_time is None:

        for day in weekdays:

            if day in text:

                days_ahead = weekdays[day] - now.weekday()

                if days_ahead <= 0:
                    days_ahead += 7

                target_time = (now + timedelta(days=days_ahead)).replace(
                    hour=9, minute=0, second=0, microsecond=0
                )
                break

    if target_time is None:
        return None

    # ---------- if time already passed ----------
    if target_time <= now:
        target_time += timedelta(days=1)

    # ---------- task extraction ----------
    task = text

    task = re.sub(
        r"\b(remind me to|remind me|set a reminder to|set reminder|reminder|i want|set a|jarvis|hey jarvis)\b",
        "",
        task,
    )

    task = re.sub(
        r"\b(in \d+ (minutes?|mins?|hours?)|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        "",
        task,
    )

    task = re.sub(
        r"\b(\d{1,2}(:\d{2})?\s*(am|pm)?)\b",
        "",
        task,
    )

    task = re.sub(r"\b(at|for|to|that|by)\b", "", task)

    task = re.sub(r"\s+", " ", task).strip()

    if not task:
        task = "do something"

    return task, target_time.strftime("%Y-%m-%d %H:%M")
