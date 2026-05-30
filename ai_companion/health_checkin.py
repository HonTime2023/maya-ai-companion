"""
Health Check-in Manager — Proactive morning/evening check-ins,
hydration nudges, and medication reminders.
Runs as daemon threads alongside the voice agent.
"""
import asyncio
import threading
import time
from datetime import datetime, date

from health_memory import (
    load_profile, update_field,
    get_log_entries, reset_hydration_if_new_day,
)


class HealthCheckinManager:
    """
    Manages proactive health background threads.
    Pass in the VoiceAgentThread instance so we can inject spoken messages.
    """

    def __init__(self, agent_thread):
        self.agent_thread = agent_thread
        self._stop = threading.Event()

    def start(self):
        """Start all proactive health threads."""
        threads = [
            threading.Thread(target=self._morning_checkin_thread, name="MorningCheckin", daemon=True),
            threading.Thread(target=self._evening_checkin_thread, name="EveningCheckin", daemon=True),
            threading.Thread(target=self._hydration_nudge_thread, name="HydrationNudge", daemon=True),
            threading.Thread(target=self._medication_reminder_thread, name="MedReminder", daemon=True),
            threading.Thread(target=self._weekly_report_thread, name="WeeklyReport", daemon=True),
        ]
        for t in threads:
            t.start()

    def stop(self):
        self._stop.set()

    def _inject(self, message: str):
        """Thread-safe injection of a spoken message into the voice agent."""
        loop = self.agent_thread.loop
        agent = self.agent_thread.agent
        if loop and not loop.is_closed() and agent and agent.is_running:
            try:
                asyncio.run_coroutine_threadsafe(
                    agent.inject_agent_message(message), loop
                )
            except Exception:
                pass

    def _name_greeting(self):
        """Return 'Good [time], Name!' greeting string."""
        profile = load_profile()
        name = profile.get("name", "")
        name_part = f", {name}" if name and name.lower() not in ("user", "") else ""
        hour = datetime.now().hour
        if hour < 12:
            period = "morning"
        elif hour < 17:
            period = "afternoon"
        else:
            period = "evening"
        return f"Good {period}{name_part}"

    # ------------------------------------------------------------------ #
    # MORNING CHECK-IN  (7am – 9am, once per day)
    # ------------------------------------------------------------------ #
    def _morning_checkin_thread(self):
        _fired_date = None
        while not self._stop.wait(60):
            now = datetime.now()
            today = date.today()

            if now.hour < 7 or now.hour >= 9:
                continue
            if _fired_date == today:
                continue

            _fired_date = today
            profile = load_profile()
            name = profile.get("name", "")
            name_part = f", {name}" if name and name.lower() not in ("user", "") else ""

            # Tailor message based on yesterday's sleep log
            yesterday_sleep = get_log_entries("sleep_log", days=1)
            if yesterday_sleep:
                hrs = yesterday_sleep[-1].get("hours", 0)
                if hrs < 6:
                    sleep_note = f"You only got {hrs} hours last night — try to rest more today."
                elif hrs >= 8:
                    sleep_note = f"You got a solid {hrs} hours last night. That is great!"
                else:
                    sleep_note = f"You logged {hrs} hours last night."
                msg = (
                    f"Good morning{name_part}! {sleep_note} "
                    f"How are you feeling today? Tell me your mood and we can track your wellness."
                )
            else:
                msg = (
                    f"Good morning{name_part}! How did you sleep last night? "
                    f"And how are you feeling today?"
                )
            self._inject(msg)

    # ------------------------------------------------------------------ #
    # EVENING CHECK-IN  (8pm – 10pm, once per day)
    # ------------------------------------------------------------------ #
    def _evening_checkin_thread(self):
        _fired_date = None
        while not self._stop.wait(60):
            now = datetime.now()
            today = date.today()

            if now.hour < 20 or now.hour >= 22:
                continue
            if _fired_date == today:
                continue

            _fired_date = today
            profile = load_profile()
            name = profile.get("name", "")
            name_part = f", {name}" if name and name.lower() not in ("user", "") else ""

            # Check for untaken medications
            meds = profile.get("medications", [])
            today_str = today.isoformat()
            taken_today = [
                e["name"] for e in profile.get("medication_log", [])
                if e.get("date") == today_str and e.get("taken")
            ]
            not_taken = [m["name"] for m in meds if m["name"] not in taken_today]

            if not_taken:
                med_list = " and ".join(not_taken)
                msg = (
                    f"Good evening{name_part}! Before you wind down, "
                    f"did you take your {med_list}? "
                    f"How was your day overall?"
                )
            else:
                msg = (
                    f"Good evening{name_part}! How are you feeling tonight? "
                    f"Do not forget to log your sleep when you wake up tomorrow."
                )
            self._inject(msg)

    # ------------------------------------------------------------------ #
    # HYDRATION NUDGE  (every 2 hours between 9am – 9pm if behind goal)
    # ------------------------------------------------------------------ #
    def _hydration_nudge_thread(self):
        _last_nudge_hour = -1
        while not self._stop.wait(300):  # check every 5 minutes
            now = datetime.now()

            if now.hour < 9 or now.hour >= 21:
                continue
            # Only nudge on odd hours: 9, 11, 13, 15, 17, 19
            if now.hour % 2 == 0:
                continue
            if now.hour == _last_nudge_hour:
                continue

            reset_hydration_if_new_day()
            profile = load_profile()
            current = profile.get("hydration_today", 0)
            goal = profile.get("hydration_goal", 8)

            # Expected glasses by this point in the day (linear from 9am to 9pm)
            hours_elapsed = max(0, now.hour - 9)
            expected = int((hours_elapsed / 12) * goal)

            if current < expected:
                remaining = goal - current
                name = profile.get("name", "")
                name_part = f", {name}" if name and name.lower() not in ("user", "") else ""
                msg = (
                    f"Hey{name_part}! Just a gentle nudge to drink some water. "
                    f"You have had {current} glasses today and need {remaining} more to hit your goal."
                )
                self._inject(msg)
                _last_nudge_hour = now.hour

    # ------------------------------------------------------------------ #
    # MEDICATION REMINDERS  (fires at scheduled time of day)
    # ------------------------------------------------------------------ #
    def _medication_reminder_thread(self):
        _reminded_today = set()
        _last_reset_date = date.today()

        while not self._stop.wait(60):
            now = datetime.now()
            today = date.today()

            # Reset tracking at midnight
            if today != _last_reset_date:
                _reminded_today.clear()
                _last_reset_date = today

            profile = load_profile()
            meds = profile.get("medications", [])

            time_map = {
                "morning": 8, "afternoon": 13, "evening": 19,
                "night": 21, "bedtime": 22,
            }

            for med in meds:
                med_name = med.get("name", "")
                times_str = med.get("times", "morning").lower()
                target_hour = time_map.get(times_str, 8)

                key = f"{today.isoformat()}_{med_name}_{times_str}"
                if key in _reminded_today:
                    continue
                if now.hour != target_hour or now.minute > 10:
                    continue

                # Check if already taken
                today_str = today.isoformat()
                taken_names = [
                    e["name"] for e in profile.get("medication_log", [])
                    if e.get("date") == today_str and e.get("taken")
                ]
                if med_name in taken_names:
                    _reminded_today.add(key)
                    continue

                name = profile.get("name", "")
                name_part = f", {name}" if name and name.lower() not in ("user", "") else ""
                dosage = med.get("dosage", "")
                dosage_part = f" {dosage}" if dosage else ""
                msg = (
                    f"Medication reminder{name_part}! "
                    f"It is time to take your {med_name}{dosage_part}. "
                    f"Say 'I took my {med_name}' when you are done."
                )
                self._inject(msg)
                _reminded_today.add(key)

    # ------------------------------------------------------------------ #
    # WEEKLY REPORT  (Sunday mornings, once per week)
    # ------------------------------------------------------------------ #
    def _weekly_report_thread(self):
        while not self._stop.wait(3600):  # check every hour
            now = datetime.now()
            # Fire Sunday between 10am-11am
            if now.weekday() != 6 or now.hour != 10:
                continue

            from health_memory import report_sent_today, mark_report_sent
            if report_sent_today():
                continue

            from health_report import generate_weekly_report
            report = generate_weekly_report()
            self._inject(report)
            mark_report_sent()

            # Also try to send via Telegram
            try:
                from telegram_service import send_telegram_message
                send_telegram_message(report)
            except Exception:
                pass
