import re
from datetime import datetime, timedelta


def parse_alarm(text):

    text = text.lower().strip()

    if not any(word in text for word in ["alarm", "wake me", "wake up"]):
        return None

    now = datetime.now()
    target_time = None
    note = "Alarm"

    # -------- relative time: "in 10 minutes" --------
    match = re.search(r"in (\d+) (minute|minutes|min|mins)", text)
    if match:
        mins = int(match.group(1))
        target_time = now + timedelta(minutes=mins)

    match = re.search(r"in (\d+) (hour|hours)", text)
    if match:
        hrs = int(match.group(1))
        target_time = now + timedelta(hours=hrs)

    # -------- explicit time --------
    if target_time is None:

        time_match = re.search(r"\b(\d{1,2})(:\d{2})?\s*(am|pm)?\b", text)

        if time_match:

            hour = int(time_match.group(1))
            minute = 0

            if time_match.group(2):
                minute = int(time_match.group(2)[1:])

            meridian = time_match.group(3)

            if meridian == "pm" and hour != 12:
                hour += 12
            if meridian == "am" and hour == 12:
                hour = 0

            if hour > 23:
                hour = hour % 24

            target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # -------- tomorrow --------
    if target_time is None and "tomorrow" in text:

        target_time = (now + timedelta(days=1)).replace(
            hour=7, minute=0, second=0, microsecond=0
        )

    # -------- weekday --------
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
                    hour=7, minute=0, second=0, microsecond=0
                )
                break

    if target_time is None:
        return None

    # -------- fix past times --------
    if target_time <= now:
        target_time += timedelta(days=1)

    # -------- note extraction --------
    note = text

    note = re.sub(
        r"\b(set alarm|alarm|wake me up|wake me|jarvis|hey jarvis)\b",
        "",
        note,
    )

    note = re.sub(
        r"\b(in \d+ (minutes?|hours?)|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        "",
        note,
    )

    note = re.sub(
        r"\b(\d{1,2}(:\d{2})?\s*(am|pm)?)\b",
        "",
        note,
    )

    note = re.sub(r"\b(at|for|to|that)\b", "", note)

    note = re.sub(r"\s+", " ", note).strip()

    if not note:
        note = "Alarm"

    return target_time.strftime("%H:%M"), note
