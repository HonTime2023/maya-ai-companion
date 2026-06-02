"""
Motion Detection Module — Raspberry Pi PIR sensor with Windows/webcam fallback.

Detection backends (auto-selected in priority order):
  1. RPi.GPIO  — real PIR sensor on Raspberry Pi (GPIO BCM pin, default 7)
  2. OpenCV    — webcam pixel-diff motion detection (no extra hardware)
  3. Simulation — manual trigger via trigger_simulated_motion() for testing

Voice-callable: start_motion_monitoring, stop_motion_monitoring,
                get_motion_status, set_motion_cooldown
"""
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

logger = logging.getLogger("AI_Companion")

# ── Backend detection ──────────────────────────────────────────────────────────
try:
    import RPi.GPIO as GPIO  # type: ignore
    _BACKEND = "gpio"
except ImportError:
    GPIO = None
    try:
        import cv2  # type: ignore
        _BACKEND = "opencv"
    except ImportError:
        cv2 = None
        _BACKEND = "simulation"

logger.info(f"[MOTION] Backend: {_BACKEND}")


# ── Event dataclass ────────────────────────────────────────────────────────────
@dataclass
class MotionEvent:
    timestamp: datetime = field(default_factory=datetime.now)
    backend: str = _BACKEND
    location: str = "main"          # room/zone label (configurable)
    consecutive_count: int = 1      # how many triggers since last cooldown


# ── Detector class ─────────────────────────────────────────────────────────────
class MotionDetector:
    """
    Background-thread motion detector.
    Calls every registered callback(MotionEvent) when motion is detected,
    respecting a cooldown period to avoid repeated rapid triggers.
    """

    DEFAULT_GPIO_PIN  = 7    # BCM GPIO 7 (physical pin 26)
    DEFAULT_COOLDOWN  = 30   # seconds between voice announcements
    OPENCV_THRESHOLD  = 5000 # pixel-diff area to count as motion

    def __init__(
        self,
        gpio_pin: int = DEFAULT_GPIO_PIN,
        cooldown_seconds: int = DEFAULT_COOLDOWN,
        location: str = "main",
    ):
        self.gpio_pin         = gpio_pin
        self.cooldown         = cooldown_seconds
        self.location         = location
        self._callbacks: List[Callable[[MotionEvent], None]] = []
        self._thread: Optional[threading.Thread] = None
        self._stop_event      = threading.Event()
        self._active          = False
        self._last_trigger    = 0.0
        self._total_count     = 0
        self._consecutive     = 0
        self._last_event: Optional[MotionEvent] = None
        self._sim_event       = threading.Event()

    # ── Public API ─────────────────────────────────────────────────────────────

    def add_callback(self, fn: Callable[[MotionEvent], None]) -> None:
        """Register a function to call on each motion event."""
        self._callbacks.append(fn)

    def start(self) -> str:
        if self._active:
            return "Motion monitoring is already running."
        self._stop_event.clear()
        self._sim_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="MotionDetector")
        self._thread.start()
        self._active = True
        logger.info(f"[MOTION] Started ({_BACKEND} backend, pin={self.gpio_pin}, cooldown={self.cooldown}s)")
        return f"Motion monitoring started using {_BACKEND} backend."

    def stop(self) -> str:
        if not self._active:
            return "Motion monitoring is not running."
        self._stop_event.set()
        self._sim_event.set()  # unblock any waiting loop
        self._active = False
        if _BACKEND == "gpio" and GPIO:
            try:
                GPIO.cleanup()
            except Exception:
                pass
        logger.info("[MOTION] Stopped")
        return "Motion monitoring stopped."

    def set_cooldown(self, seconds: int) -> str:
        try:
            seconds = max(1, int(seconds))
        except (ValueError, TypeError):
            return "Invalid cooldown value. Please say a number of seconds."
        self.cooldown = seconds
        return f"Motion cooldown set to {seconds} seconds."

    def trigger_simulated_motion(self) -> None:
        """Manually fire a motion event (used in tests and simulation mode)."""
        self._sim_event.set()

    def status(self) -> str:
        state = "active" if self._active else "inactive"
        last = (
            self._last_event.timestamp.strftime("%H:%M:%S")
            if self._last_event else "never"
        )
        return (
            f"Motion monitoring is {state}. "
            f"Backend: {_BACKEND}. "
            f"Total events today: {self._total_count}. "
            f"Last motion detected at {last}. "
            f"Cooldown: {self.cooldown} seconds."
        )

    # ── Internal run loops ─────────────────────────────────────────────────────

    def _run(self) -> None:
        if _BACKEND == "gpio":
            self._run_gpio()
        elif _BACKEND == "opencv":
            self._run_opencv()
        else:
            self._run_simulation()

    def _on_motion(self) -> None:
        """Central handler: apply cooldown, build event, fire callbacks."""
        now = time.time()
        if now - self._last_trigger < self.cooldown:
            logger.debug("[MOTION] Suppressed — within cooldown window")
            return

        self._last_trigger = now
        self._total_count += 1
        since_last = now - self._last_trigger if self._last_event else 9999
        self._consecutive = self._consecutive + 1 if since_last < 120 else 1

        event = MotionEvent(
            timestamp=datetime.now(),
            backend=_BACKEND,
            location=self.location,
            consecutive_count=self._consecutive,
        )
        self._last_event = event
        logger.info(f"[MOTION] Detected! count={self._total_count} consecutive={self._consecutive}")

        for cb in self._callbacks:
            try:
                cb(event)
            except Exception as e:
                logger.error(f"[MOTION] Callback error: {e}")

    # ── GPIO backend ───────────────────────────────────────────────────────────
    def _run_gpio(self) -> None:
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.gpio_pin, GPIO.IN)
            logger.info(f"[MOTION] GPIO ready on BCM pin {self.gpio_pin}")
            while not self._stop_event.is_set():
                if GPIO.input(self.gpio_pin):
                    self._on_motion()
                time.sleep(0.1)
        except Exception as e:
            logger.error(f"[MOTION] GPIO error: {e}")
        finally:
            try:
                GPIO.cleanup()
            except Exception:
                pass

    # ── OpenCV webcam backend ──────────────────────────────────────────────────
    def _run_opencv(self) -> None:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            logger.error("[MOTION] Could not open webcam — falling back to simulation")
            self._run_simulation()
            return

        ret, prev_frame = cap.read()
        if not ret:
            cap.release()
            self._run_simulation()
            return

        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        prev_gray = cv2.GaussianBlur(prev_gray, (21, 21), 0)
        logger.info("[MOTION] OpenCV webcam loop started")

        while not self._stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.5)
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)
            diff = cv2.absdiff(prev_gray, gray)
            thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for contour in contours:
                if cv2.contourArea(contour) > self.OPENCV_THRESHOLD:
                    self._on_motion()
                    break

            prev_gray = gray
            time.sleep(0.1)

        cap.release()
        logger.info("[MOTION] OpenCV loop ended")

    # ── Simulation backend ─────────────────────────────────────────────────────
    def _run_simulation(self) -> None:
        logger.info("[MOTION] Simulation loop running — call trigger_simulated_motion() to fire")
        while not self._stop_event.is_set():
            triggered = self._sim_event.wait(timeout=1.0)
            if triggered and not self._stop_event.is_set():
                self._sim_event.clear()
                self._on_motion()


# ── Module-level singleton ─────────────────────────────────────────────────────
_detector: Optional[MotionDetector] = None


def get_detector() -> MotionDetector:
    """Return (creating if needed) the shared MotionDetector instance."""
    global _detector
    if _detector is None:
        _detector = MotionDetector()
    return _detector


# ── Voice-callable functions ───────────────────────────────────────────────────

def start_motion_monitoring() -> str:
    """Start background motion monitoring."""
    return get_detector().start()


def stop_motion_monitoring() -> str:
    """Stop background motion monitoring."""
    return get_detector().stop()


def get_motion_status() -> str:
    """Get the current motion monitoring status."""
    return get_detector().status()


def set_motion_cooldown(seconds: int) -> str:
    """Set how many seconds must pass between motion alerts."""
    return get_detector().set_cooldown(seconds)


# ── Agent integration helper ───────────────────────────────────────────────────

def attach_agent(agent) -> None:
    """
    Wire the motion detector to the voice agent so that when motion is
    detected the agent speaks a greeting. Call this once after agent creation.
    """
    import asyncio

    def _on_motion(event: MotionEvent) -> None:
        if event.consecutive_count == 1:
            msg = "Hello! I noticed some movement. How can I help you?"
        else:
            msg = f"Welcome back. Motion detected again in the {event.location} area."

        if agent.loop and agent.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                agent.inject_agent_message(msg), agent.loop
            )
        logger.info(f"[MOTION] Agent notified: {msg}")

    detector = get_detector()
    detector.add_callback(_on_motion)
    logger.info("[MOTION] Agent callback registered")

