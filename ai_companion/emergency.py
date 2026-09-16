"""
Emergency Module — Real SOS alert system for MAYA.
Sends Telegram SOS, triggers alarm, repeats alerts every 5 minutes until cancelled.
Auto-cancels when someone replies to the Telegram bot.
"""
import asyncio
import logging
import threading
import time
from datetime import datetime

import requests

from health_memory import load_profile, get_emergency_contact, update_field

logger = logging.getLogger("AI_Companion")

_emergency_active = threading.Event()


def trigger_emergency(agent_thread=None) -> str:
    """
    Activate emergency SOS:
    - Sends a Telegram SOS message to the configured chat
    - Starts a repeat-alert thread that re-sends every 5 minutes
    - Starts a Telegram reply watcher that auto-cancels when someone responds
    - Returns a spoken confirmation for MAYA to read aloud
    """
    profile = load_profile()
    name = profile.get("name", "User")
    contact = get_emergency_contact()
    doctor = profile.get("doctor_contact")
    timestamp = datetime.now().strftime("%I:%M %p on %B %d, %Y")

    # Build Telegram SOS message (include medical info for first responders)
    conditions = profile.get("conditions", [])
    medications = [m.get("name", "") for m in profile.get("medications", [])]

    lines = [
        "🚨 SOS ALERT 🚨",
        f"From: {name}",
        f"Time: {timestamp}",
        "MAYA AI Companion has triggered an emergency alert.",
    ]
    if contact:
        lines.append(f"Emergency contact: {contact}")
    if doctor:
        lines.append(f"Doctor: {doctor}")
    if conditions:
        lines.append(f"Medical conditions: {', '.join(conditions)}")
    if medications:
        lines.append(f"Current medications: {', '.join(medications)}")
    lines.append("Please respond to this message when you have reached the person.")
    telegram_msg = "\n".join(lines)

    # Send Telegram and record the latest update_id before we send
    telegram_sent = False
    baseline_update_id = _get_latest_telegram_update_id()
    try:
        from telegram_service import send_telegram_message
        telegram_sent = send_telegram_message(telegram_msg)
    except Exception:
        pass

    # Start background threads
    _emergency_active.set()
    if agent_thread is not None:
        threading.Thread(
            target=_repeat_alert_thread,
            args=(agent_thread, name),
            daemon=True,
        ).start()
        threading.Thread(
            target=_telegram_reply_watcher,
            args=(agent_thread, baseline_update_id),
            daemon=True,
        ).start()

    # Build spoken response
    parts = ["Emergency alert activated."]
    if telegram_sent:
        parts.append("I have sent an SOS message via Telegram.")
        parts.append("I will automatically cancel the alarm once someone responds to that message.")
    else:
        if contact:
            parts.append(f"Your emergency contact is {contact} — please call them now.")
        else:
            parts.append(
                "Warning: no emergency contact is configured. "
                "You can set one by saying set my emergency contact to your number."
            )
    parts.append("You can also say I am safe or cancel emergency at any time to stop the alarm.")
    return " ".join(parts)


def cancel_emergency() -> str:
    """Stop emergency mode and alarm."""
    _emergency_active.clear()
    return "Emergency cancelled. I am glad you are safe."


def is_emergency_active() -> bool:
    return _emergency_active.is_set()


def set_doctor_contact(number: str) -> str:
    """Save doctor's phone number to health profile."""
    if not number.startswith("+") or not number[1:].isdigit():
        return "Invalid format. Use international format like +2348012345678."
    update_field("doctor_contact", number)
    return f"Doctor contact saved as {number}."


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_latest_telegram_update_id() -> int:
    """
    Fetch the current highest update_id from Telegram so the watcher
    only reacts to messages that arrive AFTER the SOS is sent.
    Returns -1 on failure.
    """
    try:
        from telegram_service import BOT_TOKEN
        if not BOT_TOKEN:
            return -1
        resp = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
            params={"limit": 1, "offset": -1},
            timeout=8,
        )
        if resp.status_code == 200:
            results = resp.json().get("result", [])
            if results:
                return results[-1]["update_id"]
    except Exception:
        pass
    return -1


def _telegram_reply_watcher(agent_thread, baseline_update_id: int):
    """
    Poll Telegram every 10 seconds for any new incoming message.
    When one arrives (meaning someone responded to the SOS), auto-cancel
    the emergency and notify the user via the voice agent.
    """
    try:
        from telegram_service import BOT_TOKEN
        if not BOT_TOKEN:
            return
    except Exception:
        return

    poll_offset = baseline_update_id + 1

    while _emergency_active.is_set():
        time.sleep(10)
        if not _emergency_active.is_set():
            break
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
                params={"offset": poll_offset, "timeout": 5},
                timeout=12,
            )
            if resp.status_code != 200:
                continue
            updates = resp.json().get("result", [])
            if not updates:
                continue

            # Advance offset to avoid re-processing
            poll_offset = updates[-1]["update_id"] + 1

            # Extract sender name from the first new message
            msg = updates[0].get("message", {})
            sender = (
                msg.get("from", {}).get("first_name")
                or msg.get("from", {}).get("username")
                or "Someone"
            )

            # Cancel emergency and stop alarm
            _emergency_active.clear()
            _stop_alarm_on_agent(agent_thread)

            # Inject spoken notification
            _inject_to_agent(
                agent_thread,
                f"{sender} has responded to your emergency message on Telegram. "
                "The emergency alarm has been cancelled. You are safe now.",
            )
            logger.info(f"[EMERGENCY] Auto-cancelled: Telegram reply from {sender}")
            break

        except Exception as e:
            logger.debug(f"[EMERGENCY] Watcher poll error: {e}")


def _repeat_alert_thread(agent_thread, name: str):
    """Re-send SOS Telegram + spoken alert every 5 minutes until cancelled."""
    count = 0
    while _emergency_active.is_set():
        time.sleep(300)  # 5 minutes
        if not _emergency_active.is_set():
            break
        count += 1
        try:
            from telegram_service import send_telegram_message
            send_telegram_message(
                f"🚨 SOS REPEAT #{count} — {name} still needs help. "
                "Reply to this message when you have reached them."
            )
        except Exception:
            pass

        _inject_to_agent(
            agent_thread,
            f"Emergency alert still active — this is repeat number {count}. "
            "Say I am safe or cancel emergency to stop the alarm.",
        )


def _stop_alarm_on_agent(agent_thread):
    """Stop the looping alarm chime on the agent thread."""
    try:
        if agent_thread is not None:
            agent_thread._alarm_active.clear()
            agent_thread._chime_stop_event.set()
    except Exception:
        pass


def _inject_to_agent(agent_thread, message: str):
    """Thread-safe inject of a spoken message into the voice agent."""
    if agent_thread is None:
        return
    try:
        loop = agent_thread.loop
        agent = agent_thread.agent
        if loop and not loop.is_closed() and agent and agent.is_running:
            asyncio.run_coroutine_threadsafe(
                agent.inject_agent_message(message), loop
            )
    except Exception:
        pass
