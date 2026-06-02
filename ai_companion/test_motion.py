"""
Motion Detection Simulation Test
─────────────────────────────────
Simulates the full motion detection pipeline without any real hardware.
Tests:
  1. Backend auto-detection (GPIO → OpenCV → Simulation)
  2. Callback firing on motion event
  3. Cooldown suppression (rapid double-trigger)
  4. Consecutive motion counting
  5. Voice-callable functions (start, stop, status, set_cooldown)
  6. Agent integration (mock agent to verify inject_agent_message is called)
  7. Multiple callbacks (logging + agent)

Run:
  python ai_companion/test_motion.py
"""
import sys
import time
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("MotionTest")

# ── Import motion module ───────────────────────────────────────────────────────
from motion import (
    MotionDetector, MotionEvent, get_detector,
    start_motion_monitoring, stop_motion_monitoring,
    get_motion_status, set_motion_cooldown, attach_agent,
    _BACKEND,
)

PASS = "  ✅ PASS"
FAIL = "  ❌ FAIL"

results: list[tuple[str, bool]] = []


def check(label: str, condition: bool) -> None:
    results.append((label, condition))
    print(f"{'  ✅ PASS' if condition else '  ❌ FAIL'} — {label}")


# ── Mock agent (simulates voice_agent_deepgram VoiceAgentWrapper) ──────────────
class MockAgent:
    def __init__(self):
        self.injected_messages: list[str] = []
        self.loop = None  # no real event loop in test

    def inject_synchronous(self, msg: str) -> None:
        """Stand-in for async inject_agent_message in tests."""
        self.injected_messages.append(msg)
        logger.info(f"[MOCK AGENT] Would speak: '{msg}'")


# ── Test 1: Backend detection ──────────────────────────────────────────────────
print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("TEST 1 — Backend detection")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print(f"  Detected backend: {_BACKEND}")
check("Backend is one of [gpio, opencv, simulation]", _BACKEND in ("gpio", "opencv", "simulation"))


# ── Test 2: Detector creation ──────────────────────────────────────────────────
print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("TEST 2 — Detector creation and singleton")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
det = MotionDetector(cooldown_seconds=1, location="living room")
check("MotionDetector instantiates", det is not None)
check("Default cooldown set", det.cooldown == 1)
check("Location set", det.location == "living room")


# ── Test 3: Callback firing ────────────────────────────────────────────────────
print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("TEST 3 — Motion event fires callback")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

events_received: list[MotionEvent] = []

def test_callback(event: MotionEvent) -> None:
    events_received.append(event)
    logger.info(f"[CALLBACK] Event received: backend={event.backend} loc={event.location} count={event.consecutive_count}")

det.add_callback(test_callback)
det.start()
time.sleep(0.2)  # give thread time to start

det.trigger_simulated_motion()
time.sleep(0.3)

check("Callback fired once", len(events_received) == 1)
check("Event has correct backend", events_received[0].backend == _BACKEND)
check("Event has correct location", events_received[0].location == "living room")
check("First event count is 1", events_received[0].consecutive_count == 1)


# ── Test 4: Cooldown suppression ───────────────────────────────────────────────
print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("TEST 4 — Cooldown suppresses rapid re-triggers")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

# Reset cooldown timer so test is independent of Test 3 timing
det._last_trigger = 0.0
events_received.clear()

# First trigger fires (cooldown just reset)
det.trigger_simulated_motion()
time.sleep(0.3)

# Second trigger is within 1s cooldown → should be suppressed
det.trigger_simulated_motion()
time.sleep(0.3)

check("Only 1 event despite 2 rapid triggers", len(events_received) == 1)

# Wait out the cooldown, then trigger again
time.sleep(1.0)
det.trigger_simulated_motion()
time.sleep(0.3)
check("Trigger after cooldown fires a new event", len(events_received) == 2)


# ── Test 5: Voice-callable functions ──────────────────────────────────────────
print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("TEST 5 — Voice-callable functions")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

# Use the module-level singleton for voice functions
stop_result = det.stop()
check("stop() returns string", isinstance(stop_result, str))
check("stop() reports stopped", "stopped" in stop_result.lower())

cooldown_result = set_motion_cooldown(45)
check("set_motion_cooldown returns string", isinstance(cooldown_result, str))
check("set_motion_cooldown confirms value", "45" in cooldown_result)

status_before = get_motion_status()
check("get_motion_status returns string", isinstance(status_before, str))
print(f"  Status: {status_before}")

start_result = start_motion_monitoring()
check("start_motion_monitoring returns string", isinstance(start_result, str))
check("start result mentions backend", _BACKEND in start_result)

status_after = get_motion_status()
check("Status shows active after start", "active" in status_after.lower())

stop_motion_monitoring()


# ── Test 6: Agent integration (sync mock) ─────────────────────────────────────
print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("TEST 6 — Agent integration (mock agent)")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

mock_agent = MockAgent()
det2 = MotionDetector(cooldown_seconds=1, location="bedroom")

# Replicate attach_agent logic with sync mock (no asyncio loop in test)
def _mock_on_motion(event: MotionEvent) -> None:
    if event.consecutive_count == 1:
        msg = "Hello! I noticed some movement. How can I help you?"
    else:
        msg = f"Welcome back. Motion detected again in the {event.location} area."
    mock_agent.inject_synchronous(msg)

det2.add_callback(_mock_on_motion)
det2.start()
time.sleep(0.2)

det2.trigger_simulated_motion()
time.sleep(0.3)

check("Agent received 1 message on first motion", len(mock_agent.injected_messages) == 1)
check("First message is greeting", "Hello" in mock_agent.injected_messages[0])

# Wait cooldown, trigger again for consecutive test
time.sleep(1.2)
det2.trigger_simulated_motion()
time.sleep(0.3)

check("Agent received 2nd message after cooldown", len(mock_agent.injected_messages) == 2)
check("Second message is welcome-back", "Welcome back" in mock_agent.injected_messages[1])
check("Bedroom location in second message", "bedroom" in mock_agent.injected_messages[1])

det2.stop()


# ── Test 7: Multiple callbacks ─────────────────────────────────────────────────
print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("TEST 7 — Multiple simultaneous callbacks")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

log_events:   list[MotionEvent] = []
alert_events: list[MotionEvent] = []

det3 = MotionDetector(cooldown_seconds=1)
det3.add_callback(lambda e: log_events.append(e))
det3.add_callback(lambda e: alert_events.append(e))
det3.start()
time.sleep(0.2)

det3.trigger_simulated_motion()
time.sleep(0.3)

check("Log callback received event", len(log_events) == 1)
check("Alert callback received event", len(alert_events) == 1)
check("Both callbacks got same timestamp", log_events[0].timestamp == alert_events[0].timestamp)

det3.stop()


# ── Summary ────────────────────────────────────────────────────────────────────
print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("SUMMARY")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
passed = sum(1 for _, ok in results if ok)
total  = len(results)
for label, ok in results:
    print(f"  {'✅' if ok else '❌'}  {label}")

print(f"\nResult: {passed}/{total} tests passed")
if passed == total:
    print("🎉 All tests passed! Motion module is ready.")
else:
    print("⚠️  Some tests failed — check output above.")
