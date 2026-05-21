#!/usr/bin/env python3
"""
Deepgram Voice Agent API - Unified Real-Time Voice Agent
Handles STT, LLM, TTS, and Function Calling over a single WebSocket connection.

This replaces the fragmented approach (separate STT → LLM → TTS) with a single
unified pipeline matching the Deepgram playground architecture.

Architecture:
1. Open WebSocket to Deepgram Voice Agent
2. Configure STT (nova-2), LLM (OpenAI), TTS (Aura), and functions
3. Stream user audio in
4. Receive agent audio out + function calls
5. Execute functions and respond
"""

import asyncio
import json
import logging
import os
import sounddevice as sd
import numpy as np
import websockets
from datetime import datetime
from typing import Optional, Callable, Dict, Any
import threading
import queue

try:
    from logger import logger
except ImportError:
    logger = logging.getLogger("VoiceAgent")
    logging.basicConfig(level=logging.INFO)

# ===== AUDIO CONFIG =====
SAMPLE_RATE = 16000        # Mic INPUT sample rate (stays 16000)
OUTPUT_SAMPLE_RATE = 24000  # Agent TTS OUTPUT sample rate (Deepgram default is 24000)
CHANNELS = 1
FRAME_SIZE = 512
# Device indices — run test_devices.py to find the right index for your machine
# On this Dell: device=1 (MME) returns silence; device=5 (DirectSound) works
MIC_DEVICE = 5
SPEAKER_DEVICE = None  # None = default output device

# VAD thresholds for speech detection
VOLUME_THRESHOLD = 50
NOISE_THRESHOLD = 10
SILENCE_THRESHOLD = 8


def get_rms_volume(audio_chunk):
    """Calculate RMS volume of audio chunk (normalized float32)."""
    if len(audio_chunk) == 0:
        return 0
    rms = np.sqrt(np.mean(audio_chunk ** 2))
    return rms * 1000


class DeepgramVoiceAgent:
    """
    Unified Voice Agent using Deepgram Voice Agent API.
    Single WebSocket connection for listen → think → speak pipeline.
    """

    def __init__(self, deepgram_api_key: str, openai_api_key: str):
        self.deepgram_api_key = deepgram_api_key
        self.openai_api_key = openai_api_key
        self.ws = None
        self.audio_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self.is_running = False
        self.functions_registry = {}
        self.agent_speaking = False
        self.user_speaking = False
        self._tts_queue = queue.Queue()  # TTS audio chunks streamed in real time

    def register_function(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: Callable,
        client_side: bool = True,
    ):
        """
        Register a function that the agent can call.
        
        Args:
            name: Function name
            description: What the function does
            parameters: JSON schema for parameters
            handler: Callable that executes the function
            client_side: If True, client executes; if False, server executes
        """
        self.functions_registry[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "handler": handler,
            "client_side": client_side,
        }

    async def connect(self, user_greeting: str = "Hello! How can I help you today?"):
        """Connect to Deepgram Voice Agent API and configure."""
        uri = "wss://agent.deepgram.com/v1/agent/converse"
        
        headers = {
            "Authorization": f"Token {self.deepgram_api_key}",
        }

        try:
            logger.info(f"🔌 Connecting to {uri}...")
            self.ws = await websockets.connect(
                uri,
                additional_headers=headers,
                ping_interval=None,  # Deepgram manages its own heartbeat
            )
            logger.info("✅ Connected to Deepgram Voice Agent")

            # Send configuration
            config = self._build_config(user_greeting)
            await self.ws.send(json.dumps(config))
            logger.info("📝 Configuration sent")

            self.is_running = True
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            raise

    async def disconnect(self):
        """Disconnect from the WebSocket."""
        if self.ws:
            self.is_running = False
            await self.ws.close()
            logger.info("🔌 Disconnected from Deepgram Voice Agent")

    def _build_config(self, greeting: str) -> Dict[str, Any]:
        """Build the initial settings configuration for the agent."""
        
        # Build function definitions
        functions = []
        for func_name, func_def in self.functions_registry.items():
            functions.append({
                "name": func_name,
                "description": func_def["description"],
                "parameters": func_def["parameters"],
            })

        config = {
            "type": "Settings",
            "audio": {
                "input": {
                    "encoding": "linear16",
                    "sample_rate": SAMPLE_RATE,
                },
                "output": {
                    "encoding": "linear16",
                    "sample_rate": OUTPUT_SAMPLE_RATE,
                },
            },
            "agent": {
                "language": "en",
                "context": {
                    "messages": []
                },
                "listen": {
                    "provider": {
                        "type": "deepgram",
                        "model": "nova-3"
                    }
                },
                "think": {
                    "provider": {
                        "type": "open_ai",
                        "model": "gpt-4o-mini",
                        "temperature": 0.7,
                    },
                    "functions": functions,
                    "prompt": (
                        "You are JARVIS, a warm, intelligent AI companion. "
                        "CRITICAL SPEECH RULES — follow these at all times: "
                        "1. NEVER use markdown formatting. No asterisks (**bold**), no underscores (_italic_), no dash lists (- item), no numbered lists (1. item), no pound signs (# header). Speak in plain natural flowing sentences only. "
                        "2. Be concise and warm. Give short, friendly answers like a trusted companion talking out loud — not like a written document. "
                        "3. Address the user by their first name whenever you know it. "
                        "4. If the user says their name (e.g. 'my name is Alex', 'call me Alex', 'I am Alex', 'change my name to Alex'), call the set_name function immediately with that name. "
                        "5. If the user mentions where they live or their city (e.g. 'I live in Lagos', 'I am in Abuja', 'my city is Kano'), call the set_location function with that city name. "
                        "6. For weather, ALWAYS call get_weather — never guess the weather. "
                        "7. For time or date, always call get_time or get_date. "
                        "8. Respond naturally when greeted with 'Hello Jarvis', 'Hey Jarvis', or just 'Jarvis'. "
                        "9. When a reminder is injected, speak it naturally and warmly, like: 'Just a heads up — it's time to take your medication!' "
                    ),
                },
                "speak": {
                    "provider": {
                        "type": "deepgram",
                        "model": "aura-2-thalia-en"
                    }
                },
                "greeting": greeting,
            },
        }
        return config

    async def inject_agent_message(self, message: str):
        """Inject a message so the agent speaks it aloud (e.g. for reminders)."""
        if self.ws and self.is_running:
            try:
                await self.ws.send(json.dumps({"type": "InjectAgentMessage", "message": message}))
                logger.info(f"[INJECT] Agent message injected: {message[:60]}")
            except Exception as e:
                logger.error(f"[INJECT] Failed: {e}")

    async def send_audio(self, audio_data: bytes):
        """Send audio data to the agent as binary WebSocket frame."""
        if not self.ws or not audio_data or not self.is_running:
            return
        try:
            await self.ws.send(audio_data)
            logger.debug(f"Sent {len(audio_data)} bytes of audio")
        except Exception:
            # Silently stop sending when connection is closed
            self.is_running = False

    async def receive_messages(self):
        """Receive and process messages from the agent."""
        logger.info("📨 Message receive loop started")
        try:
            while self.is_running:
                try:
                    message = await self.ws.recv()
                    if isinstance(message, bytes):
                        # Binary frame = TTS audio — send straight to playback queue
                        self._tts_queue.put(message)
                        print(f"[TTS] Binary frame queued: {len(message)} bytes (queue={self._tts_queue.qsize()})", flush=True)
                        logger.info(f"🎵 Binary TTS frame queued: {len(message)} bytes (queue size: {self._tts_queue.qsize()})")
                    else:
                        data = json.loads(message)
                        await self._handle_message(data)
                except websockets.exceptions.ConnectionClosed:
                    logger.info("📨 WebSocket connection closed")
                    break
                except Exception as e:
                    if self.is_running:
                        logger.error(f"Error receiving message: {e}")
        except Exception as e:
            logger.error(f"Receive loop error: {e}")
        finally:
            logger.info("📨 Message receive loop ended")

    async def _handle_message(self, message: Dict[str, Any]):
        """Handle incoming messages from the agent."""
        msg_type = message.get("type")

        if msg_type == "Welcome":
            logger.info(f"✅ Welcome: {message.get('request_id')}")

        elif msg_type == "SettingsApplied":
            logger.info("✅ Settings applied")

        elif msg_type == "UserStartedSpeaking":
            self.user_speaking = True
            # Barge-in: drain TTS queue so no more chunks are played
            drained = 0
            while not self._tts_queue.empty():
                try:
                    self._tts_queue.get_nowait()
                    drained += 1
                except queue.Empty:
                    break
            self.agent_speaking = False
            logger.info(f"🎤 User started speaking (barge-in, drained {drained} chunks)")

        elif msg_type == "AgentThinking":
            logger.info(f"🤔 Agent thinking: {message.get('content', '')}")

        elif msg_type == "ConversationText":
            role = message.get("role", "unknown")
            content = message.get("content", "")
            logger.info(f"💬 [{role}] {content}")
            self.response_queue.put({"role": role, "content": content})

        elif msg_type == "AgentStartedSpeaking":
            self.agent_speaking = True
            latency = message.get("total_latency", 0)
            logger.info(f"🔊 Agent started speaking (latency: {latency}s)")

        elif msg_type == "Audio":
            # Raw audio data from agent (base64 or hex encoded)
            audio_data = message.get("data", "")
            if audio_data:
                try:
                    # Decode from hex
                    audio_bytes = bytes.fromhex(audio_data)
                    self.response_queue.put({"type": "audio", "data": audio_bytes})
                except Exception as e:
                    logger.error(f"Error decoding audio: {e}")

        elif msg_type == "AgentAudioDone":
            logger.info(f"🔊 AgentAudioDone (queue size: {self._tts_queue.qsize()})")

        elif msg_type == "FunctionCallRequest":
            await self._handle_function_call(message)

        elif msg_type == "Error":
            error_msg = message.get("description", "Unknown error")
            code = message.get("code", "")
            logger.error(f"❌ Agent error [{code}]: {error_msg}")
            # Only stop on fatal configuration errors
            if code in ("INVALID_SETTINGS", "AUTH_ERROR"):
                self.is_running = False

        elif msg_type == "Warning":
            warn_msg = message.get("description", "Unknown warning")
            logger.warning(f"⚠️ Agent warning: {warn_msg}")

    async def _handle_function_call(self, message: Dict[str, Any]):
        """Handle function call requests from the agent."""
        functions = message.get("functions", [])
        
        for func_call in functions:
            func_id = func_call.get("id")
            func_name = func_call.get("name")
            arguments = json.loads(func_call.get("arguments", "{}"))
            client_side = func_call.get("client_side", True)

            logger.info(f"📞 Function call: {func_name}({arguments})")

            # Execute client-side functions
            if client_side and func_name in self.functions_registry:
                try:
                    handler = self.functions_registry[func_name]["handler"]
                    result = handler(**arguments)
                    
                    # Send response back
                    response = {
                        "type": "FunctionCallResponse",
                        "name": func_name,
                        "id": func_id,
                        "content": json.dumps(result),
                    }
                    await self.ws.send(json.dumps(response))
                    logger.info(f"✅ Function result sent: {func_name}")
                except Exception as e:
                    logger.error(f"Error executing function {func_name}: {e}")

    def _mic_reader_thread(self, mic_queue: queue.Queue):
        """Background thread: reads mic audio into a queue using sounddevice (more reliable on Windows)."""
        import time as _time

        def _audio_callback(indata: np.ndarray, frames: int, time_info, status):
            if status:
                logger.warning(f"[MIC] sounddevice status: {status}")
            # indata is float32 (frames, channels) — take channel 0, convert to int16 bytes
            mono = indata[:, 0] if indata.ndim > 1 else indata.flatten()
            pcm = (mono * 32767.0).clip(-32768, 32767).astype(np.int16)
            try:
                mic_queue.put_nowait(pcm.tobytes())
            except queue.Full:
                pass  # drop stale frame — rate limiter in listening loop handles pacing

        try:
            logger.info(f"[MIC] Opening sounddevice input stream at {SAMPLE_RATE}Hz, blocksize={FRAME_SIZE}")
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=FRAME_SIZE,
                callback=_audio_callback,
            ):
                logger.info("[MIC] Sounddevice stream open — listening for speech")
                while self.is_running:
                    _time.sleep(0.05)
        except Exception as e:
            logger.error(f"[MIC] Sounddevice mic error: {e}")
        finally:
            mic_queue.put(None)  # sentinel to signal shutdown

    async def run_listening_loop(self):
        """
        Continuously stream raw PCM audio to Deepgram Voice Agent.
        Mic capture runs in a background thread so asyncio is never blocked.
        """
        logger.info("🎤 Audio listening loop started")
        mic_queue: queue.Queue = queue.Queue(maxsize=5)  # small buffer — discard stale frames to avoid burst-sending

        mic_thread = threading.Thread(target=self._mic_reader_thread, args=(mic_queue,), daemon=True)
        mic_thread.start()

        FRAME_DURATION = FRAME_SIZE / SAMPLE_RATE  # seconds per frame (0.032s = 32ms)

        try:
            loop = asyncio.get_event_loop()
            next_send_time = loop.time()
            _rms_log_counter = 0
            while self.is_running:
                # Non-blocking get from the mic queue via executor
                audio_bytes = await loop.run_in_executor(None, mic_queue.get)
                if audio_bytes is None:
                    break  # sentinel — mic thread ended

                # Rate limit: enforce real-time sending — never faster than 1 frame per 32ms.
                now = loop.time()
                wait = next_send_time - now
                if wait > 0:
                    await asyncio.sleep(wait)
                next_send_time = max(loop.time(), next_send_time) + FRAME_DURATION

                # Log RMS every ~2 seconds so we can see if real speech is being captured
                _rms_log_counter += 1
                if _rms_log_counter % 62 == 0:
                    samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
                    rms = float(np.sqrt(np.mean(samples ** 2)))
                    logger.info(f"[MIC] agent_speaking={self.agent_speaking}  mic_rms={rms:.1f}  (>200=speech)")

                if self.agent_speaking:
                    await self.send_audio(bytes(len(audio_bytes)))
                else:
                    await self.send_audio(audio_bytes)

        except Exception as e:
            logger.error(f"Error in listening loop: {e}")
        finally:
            self.is_running = False  # signal mic thread and receive loop to stop
            # Close websocket to unblock ws.recv() in receive_messages()
            if self.ws:
                try:
                    asyncio.ensure_future(self.ws.close())
                except Exception:
                    pass
            logger.info("🎤 Audio listening loop ended")

    def _streaming_playback_worker(self):
        """Background thread: streams TTS chunks to speakers in real time via OutputStream."""
        logger.info("🔊 Streaming playback worker started")
        try:
            with sd.OutputStream(
                samplerate=OUTPUT_SAMPLE_RATE,
                channels=CHANNELS,
                dtype='int16',
            ) as stream:
                idle_ticks = 0
                while self.is_running:
                    try:
                        chunk_bytes = self._tts_queue.get(timeout=0.1)
                        audio_int16 = np.frombuffer(chunk_bytes, dtype=np.int16)
                        stream.write(audio_int16)
                        self.agent_speaking = True
                        idle_ticks = 0
                        logger.info(f"🔈 Wrote {len(audio_int16)} samples to OutputStream")
                    except queue.Empty:
                        idle_ticks += 1
                        if idle_ticks >= 5 and self.agent_speaking:
                            # 0.5s of silence means agent finished speaking
                            self.agent_speaking = False
                            logger.info("🔊 Agent finished speaking")
        except Exception as e:
            logger.error(f"Streaming playback error: {e}")
        finally:
            self.agent_speaking = False
            logger.info("🔊 Streaming playback worker stopped")

    def _playback_thread(self):
        """
        Dedicated thread for audio playback — avoids asyncio blocking and
        chunk-size mismatches that cause scrambled/distorted output.
        Accumulates incoming PCM frames into a buffer and drains continuously.
        """
        import time as _time
        logger.info("🔊 Playback thread started")
        audio_buffer = np.array([], dtype=np.float32)
        PLAY_CHUNK = 1600  # 100ms at 16kHz — write in fixed-size chunks

        try:
            with sd.OutputStream(
                channels=CHANNELS,
                samplerate=SAMPLE_RATE,
                dtype="float32",
            ) as stream:
                while self.is_running:
                    # Drain the queue into buffer
                    while True:
                        try:
                            response = self.response_queue.get_nowait()
                            if isinstance(response, dict) and response.get("type") == "audio":
                                raw = response["data"]
                                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32767.0
                                audio_buffer = np.concatenate([audio_buffer, samples])
                        except queue.Empty:
                            break

                    # Write full chunks to the stream
                    while len(audio_buffer) >= PLAY_CHUNK:
                        chunk = audio_buffer[:PLAY_CHUNK].reshape(-1, CHANNELS)
                        stream.write(chunk)
                        audio_buffer = audio_buffer[PLAY_CHUNK:]

                    # Flush tail or sleep
                    if len(audio_buffer) > 0:
                        # Brief wait to let more chunks arrive
                        _time.sleep(0.02)
                        if self.response_queue.empty():
                            stream.write(audio_buffer.reshape(-1, CHANNELS))
                            audio_buffer = np.array([], dtype=np.float32)
                    else:
                        _time.sleep(0.01)
        except Exception as e:
            logger.error(f"Playback error: {e}")
        finally:
            logger.info("🔊 Playback thread ended")

    async def play_response_audio(self):
        """Launch the playback thread and wait for it to finish."""
        logger.info("🔊 Ready to play agent responses")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._playback_thread)

    async def run(self):
        """
        Main run loop: connect, listen, receive, speak in parallel.
        This is the unified pipeline replacing fragmented approach.
        """
        try:
            await self.connect()
            logger.info("🚀 Starting parallel tasks...")

            # Start streaming playback worker in background thread
            playback_worker = threading.Thread(
                target=self._streaming_playback_worker, daemon=True
            )
            playback_worker.start()

            # Run two tasks in parallel:
            # 1. Listen for user audio and send to agent
            # 2. Receive agent responses and handle function calls
            tasks = [
                self.listening_loop(),
                self.receive_messages(),
            ]
            
            logger.info("✅ All tasks started, waiting for completion...")
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Task {i} exited with exception: {result}")
                else:
                    logger.info(f"Task {i} completed")
                    
        except KeyboardInterrupt:
            logger.info("⏹️ Stopping voice agent...")
        except Exception as e:
            logger.error(f"Voice agent error: {e}")
        finally:
            await self.disconnect()

    async def listening_loop(self):
        """Alias for run_listening_loop for cleaner code."""
        await self.run_listening_loop()


# ===== SYNCHRONOUS WRAPPER FOR TKINTER INTEGRATION ==================

class VoiceAgentThread(threading.Thread):
    """
    Run Deepgram Voice Agent in a background thread.
    Provides synchronous interface for Tkinter UI.
    """

    def __init__(
        self,
        deepgram_api_key: str,
        openai_api_key: str,
        on_transcript: Callable = None,
        on_audio_play: Callable = None,
    ):
        super().__init__(daemon=True)
        self.agent = DeepgramVoiceAgent(deepgram_api_key, openai_api_key)
        self.on_transcript = on_transcript
        self.on_audio_play = on_audio_play
        self._stop_event = threading.Event()
        self.loop = None

    def register_function(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: Callable,
        client_side: bool = True,
    ):
        """Register a function (must be called before thread starts)."""
        self.agent.register_function(name, description, parameters, handler, client_side)

    def _alarm_checker_thread(self):
        """Background thread: checks alarms/reminders every 5s and fires audio+speech."""
        import time as _time
        import winsound
        from pathlib import Path

        # Regular alarm/reminder chime — pleasant tone
        alarm_chime_wav = r"C:\Windows\Media\Alarm01.wav"
        # Emergency sound — kept for the emergency feature
        emergency_wav = str(Path(__file__).parent / "alarm.wav")  # noqa: F841

        # Fall back to emergency sound if chime file is missing
        if not Path(alarm_chime_wav).exists():
            alarm_chime_wav = emergency_wav

        while not self._stop_event.is_set():
            _time.sleep(5)
            try:
                from reminders import check_reminders
                from alarms import check_alarms

                # --- REMINDERS: chime + agent speaks the message ---
                due_reminders = check_reminders()
                for msg in due_reminders:
                    logger.info(f"[REMINDER] Due: {msg}")
                    try:
                        winsound.PlaySound(alarm_chime_wav, winsound.SND_FILENAME | winsound.SND_ASYNC)
                    except Exception as e:
                        logger.warning(f"[ALARM SOUND] {e}")
                    if self.loop and not self.loop.is_closed():
                        speak_text = f"Reminder for you: {msg}"
                        asyncio.run_coroutine_threadsafe(
                            self.agent.inject_agent_message(speak_text), self.loop
                        )

                # --- ALARMS: chime only (no speech) ---
                due_alarms = check_alarms()
                for note in due_alarms:
                    logger.info(f"[ALARM] Due: {note}")
                    try:
                        winsound.PlaySound(alarm_chime_wav, winsound.SND_FILENAME)
                    except Exception as e:
                        logger.warning(f"[ALARM SOUND] {e}")

            except Exception as e:
                logger.error(f"[ALARM CHECKER] Error: {e}")

    def run(self):
        """Run the agent in the background thread."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # Start background alarm/reminder checker
        alarm_thread = threading.Thread(target=self._alarm_checker_thread, daemon=True)
        alarm_thread.start()

        try:
            self.loop.run_until_complete(self.agent.run())
        except Exception as e:
            logger.error(f"Agent thread error: {e}")
        finally:
            self.loop.close()

    def stop(self):
        """Stop the agent."""
        self._stop_event.set()
        self.agent.is_running = False
        # Close websocket to unblock ws.recv() in receive_messages
        if self.agent.ws and self.loop and not self.loop.is_closed():
            asyncio.run_coroutine_threadsafe(self.agent.ws.close(), self.loop)


def create_voice_agent_with_functions() -> VoiceAgentThread:
    """
    Factory function to create a configured Voice Agent with command functions.
    Registers all command handlers as callable functions.
    """
    from command_handlers import (
        handle_time_command,
        handle_date_command,
        handle_weather_command,
        handle_check_alarms,
        handle_set_alarm_direct,
        handle_check_reminders,
        handle_set_reminder_direct,
        handle_set_name,
        handle_set_location,
    )
    from user_manager import get_current_user

    api_key_deepgram = os.getenv("DEEPGRAM_API_KEY")
    api_key_openai = os.getenv("OPENAI_API_KEY")

    if not api_key_deepgram or not api_key_openai:
        raise ValueError("Missing API keys in .env file")

    agent = VoiceAgentThread(api_key_deepgram, api_key_openai)

    # Register command functions
    agent.register_function(
        name="get_time",
        description="Get the current time",
        parameters={"type": "object", "properties": {}},
        handler=lambda: handle_time_command(""),
        client_side=True,
    )

    agent.register_function(
        name="get_date",
        description="Get today's date",
        parameters={"type": "object", "properties": {}},
        handler=lambda: handle_date_command(""),
        client_side=True,
    )

    agent.register_function(
        name="get_weather",
        description="Get current weather for user's location",
        parameters={"type": "object", "properties": {}},
        handler=lambda: handle_weather_command(""),
        client_side=True,
    )

    agent.register_function(
        name="check_alarms",
        description="Check all set alarms",
        parameters={"type": "object", "properties": {}},
        handler=lambda: handle_check_alarms(""),
        client_side=True,
    )

    agent.register_function(
        name="set_alarm",
        description="Set a new alarm",
        parameters={
            "type": "object",
            "properties": {
                "time": {"type": "string", "description": "Time for alarm (e.g., '7:00 AM')"},
                "label": {"type": "string", "description": "Optional label for alarm"},
            },
            "required": ["time"],
        },
        handler=lambda time, label="": handle_set_alarm_direct(time, label),
        client_side=True,
    )

    agent.register_function(
        name="check_reminders",
        description="Check all set reminders",
        parameters={"type": "object", "properties": {}},
        handler=lambda: handle_check_reminders(""),
        client_side=True,
    )

    agent.register_function(
        name="set_reminder",
        description="Set a new reminder",
        parameters={
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "What to remind about"},
                "time": {"type": "string", "description": "When to remind (e.g., '5 PM' or 'in 30 minutes')"},
            },
            "required": ["task"],
        },
        handler=lambda task, time="": handle_set_reminder_direct(task, time),
        client_side=True,
    )

    agent.register_function(
        name="set_name",
        description="Save the user's name so JARVIS can address them personally",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The user's first name"},
            },
            "required": ["name"],
        },
        handler=lambda name: handle_set_name(name),
        client_side=True,
    )

    agent.register_function(
        name="set_location",
        description="Save the user's city/location for weather and local info",
        parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "The user's city or location"},
            },
            "required": ["city"],
        },
        handler=lambda city: handle_set_location(city),
        client_side=True,
    )

    return agent
