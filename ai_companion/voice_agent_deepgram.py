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
                        "1. NEVER use markdown formatting of any kind. No asterisks (*), no double asterisks (**), no underscores, no dashes for lists, no numbered lists, no pound signs. The TTS will speak every character literally so asterisks will be heard as 'asterisk'. Use only plain natural sentences. "
                        "2. Be concise and warm. Give short, friendly answers like a trusted companion talking out loud — not like a written document. "
                        "3. Address the user by their first name whenever you know it. "
                        "4. If the user says their name (e.g. 'my name is Alex', 'call me Alex', 'I am Alex', 'change my name to Alex'), call the set_name function immediately with that name. "
                        "5. If the user mentions where they live or their city (e.g. 'I live in Lagos', 'I am in Abuja', 'my city is Kano'), call the set_location function with that city name. "
                        "6. For weather questions: call get_weather for current/today's weather. Call get_weather_forecast for tomorrow or any future day — never guess. "
                        "7. For time or date, always call get_time or get_date. "
                        "8. Respond naturally when greeted with 'Hello Jarvis', 'Hey Jarvis', or just 'Jarvis'. "
                        "9. When a reminder or alarm is injected, speak it naturally and warmly, like: 'Just a heads up — your alarm is going off!' "
                        "10. When the user says anything like 'alarm off', 'stop alarm', 'stop the alarm', 'dismiss alarm', or 'silence alarm', call the stop_alarm function immediately. "
                        "11. When the user says anything like 'reminder off', 'stop reminder', 'dismiss reminder', or 'silence reminder', call the stop_reminder function immediately. "
                        "12. When an alarm or reminder notification is injected and you speak it, do NOT call any other functions. Simply speak the notification warmly and wait for the user. "
                        "13. When you receive weather data from get_weather or get_weather_forecast, always translate it into friendly everyday language. Tell the user what to expect and what to do — like 'it will be hot and humid, stay hydrated' or 'there is a good chance of rain, carry an umbrella'. Never just read numbers — make it feel helpful and human. "
                        "14. NEVER say any acknowledgment or filler phrase before or after calling a function. No 'Let me check', 'Sure', 'Give me a second', 'Let me pull that up', 'Of course'. Call the function silently and speak only when you have the final answer. "
                        "15. When listing multiple days or items, speak in flowing sentences. Example: 'Monday will be hot and sunny, Tuesday looks rainy so carry an umbrella, and Wednesday will cool down.' Never use bullet points or line breaks. "
                        "16. Health tracking: when the user mentions sleep, water, mood, symptoms, exercise, or medication, call the appropriate health function to log it. Examples: 'I slept 7 hours' → call log_sleep. 'I drank 2 glasses of water' → call log_water. 'I am feeling anxious' → call log_mood. 'I have a headache' → call log_symptom. 'I went for a run for 30 minutes' → call log_exercise. 'I took my Metformin' → call log_medication_taken. "
                        "17. When the user asks 'how am I doing health-wise', 'health summary', or 'my wellness score', call get_health_summary or get_wellness_score. "
                        "18. When the user says things like 'add Metformin to my medications' or 'I take Lisinopril in the morning', call add_medication. When the user says 'I have diabetes' or 'I have hypertension', call add_health_condition. "
                        "19. EMERGENCY: if the user says anything like 'emergency', 'help me', 'I need help', 'call for help', 'SOS', 'I am not okay', immediately call trigger_emergency. This is the highest priority action. Do not call trigger_emergency again if an emergency is already active. "
                        "20. CANCEL EMERGENCY: if the user says any of these — 'cancel emergency', 'stop emergency', 'stop the alarm', 'I am safe', 'I am okay', 'I am okay now', 'all clear', 'false alarm', 'I am fine', 'stop alarm', 'disable emergency' — immediately call cancel_emergency. Do this even if the emergency was auto-cancelled by a Telegram reply. "
                        "21. SPOTIFY MUSIC: when the user says play [song, artist, or playlist], call play_spotify with the query. For a specific artist say 'play songs by [artist]' → call play_spotify_artist. For pause → pause_spotify. For resume → resume_spotify. For next or skip → skip_track. For previous or go back → previous_track. For volume → set_spotify_volume with the percent number. To know what is playing → get_now_playing. Never guess the playback state — always call the function. "
                        "22. TELEGRAM MESSAGING: when the user says send a message via Telegram, message someone, tell someone that, or send a Telegram saying, call send_telegram_message with the message text. When the user says send my health report to Telegram → call send_health_report_telegram. When asked if Telegram is set up or working → call check_telegram_status. "
                        "23. HEALTH NEWS: when the user asks for health news, health headlines, or news about a specific health topic like 'cancer news' or 'diabetes news', call get_health_news or get_health_news_by_topic with the topic keyword. "
                        "24. MOTION SENSOR: when the user says 'start motion monitoring', 'watch for motion', 'enable motion detection' → call start_motion_monitoring. 'Stop motion monitoring' → call stop_motion_monitoring. 'Motion status' or 'is motion on' → call get_motion_status. 'Set motion cooldown to N seconds' → call set_motion_cooldown. "
                        "25. SETTING REMINDERS: when the user asks to set a reminder but does NOT say what it is for — for example 'set a reminder in 30 minutes' or 'remind me in an hour' — you MUST ask 'What would you like to be reminded about?' before calling set_reminder. Wait for their answer, then call set_reminder with both the task and the time. If the user already includes the task in the same sentence — for example 'remind me to take my medication in 30 minutes' — call set_reminder directly without asking. "
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
                    # Always send a response so the LLM isn't left hanging
                    try:
                        err_resp = {
                            "type": "FunctionCallResponse",
                            "name": func_name,
                            "id": func_id,
                            "content": json.dumps(f"Sorry, I couldn't get that information right now."),
                        }
                        await self.ws.send(json.dumps(err_resp))
                    except Exception:
                        pass

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
        self._alarm_active = threading.Event()    # set while alarm chime is looping
        self._reminder_active = threading.Event() # set while reminder chime is looping
        self._current_reminder_msg = ""           # reminder text to repeat
        self._chime_stop_event = threading.Event()  # set to stop the looping chime
        self._chime_stop_event.set()                # not playing initially
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
        import re as _re
        from pathlib import Path

        # Regular alarm/reminder chime — pleasant tone (loops until stopped)
        alarm_chime_wav = r"C:\Users\Dell\Downloads\AI_Companion\ai_companion\Alarm01.wav"
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

                # --- REMINDERS: loop chime + nagger speaks message every 15s ---
                due_reminders = check_reminders()
                for msg in due_reminders:
                    logger.info(f"[REMINDER] Due: {msg}")
                    # Convert first-person pronouns to second-person for agent speech
                    msg = _re.sub(r"\bmy\b", "your", msg, flags=_re.IGNORECASE)
                    msg = _re.sub(r"\bmyself\b", "yourself", msg, flags=_re.IGNORECASE)
                    msg = _re.sub(r"\bI'm\b", "you're", msg, flags=_re.IGNORECASE)
                    msg = _re.sub(r"\bI'll\b", "you'll", msg, flags=_re.IGNORECASE)
                    msg = _re.sub(r"\bI've\b", "you've", msg, flags=_re.IGNORECASE)
                    msg = _re.sub(r"\bI\b", "you", msg)
                    if not self._reminder_active.is_set():
                        self._reminder_active.set()
                        self._current_reminder_msg = msg
                        self._chime_stop_event.set()
                        _time.sleep(0.05)
                        self._chime_stop_event.clear()
                        threading.Thread(
                            target=self._chime_loop_thread,
                            args=(alarm_chime_wav,),
                            daemon=True,
                        ).start()
                        # Start nagger thread that repeats the reason every 15s
                        nag = threading.Thread(
                            target=self._reminder_nagger_thread, args=(msg,), daemon=True
                        )
                        nag.start()
                    if self.loop and not self.loop.is_closed():
                        try:
                            from user_manager import get_current_user as _gcu
                            _raw = _gcu().get_name()
                            _uname = _raw if _raw and _raw.lower() != "user" else ""
                        except Exception:
                            _uname = ""
                        _hi = f"Hey {_uname}" if _uname else "Hey"
                        speak_text = (
                            f"{_hi}, you asked me to remind you to {msg}. "
                            f"Say reminder off when you are done."
                        )
                        asyncio.run_coroutine_threadsafe(
                            self.agent.inject_agent_message(speak_text), self.loop
                        )

                # --- ALARMS: loop chime + agent speaks the label ---
                due_alarms = check_alarms()
                for note in due_alarms:
                    logger.info(f"[ALARM] Due: {note}")
                    if not self._alarm_active.is_set():
                        self._alarm_active.set()
                        self._chime_stop_event.set()
                        _time.sleep(0.05)
                        self._chime_stop_event.clear()
                        threading.Thread(
                            target=self._chime_loop_thread,
                            args=(alarm_chime_wav,),
                            daemon=True,
                        ).start()
                    if self.loop and not self.loop.is_closed():
                        speak_text = f"Your alarm is going off: {note}. Say 'alarm off' to stop it."
                        asyncio.run_coroutine_threadsafe(
                            self.agent.inject_agent_message(speak_text), self.loop
                        )

            except Exception as e:
                logger.error(f"[ALARM CHECKER] Error: {e}")

    def _reminder_nagger_thread(self, msg: str):
        """Repeats the reminder message every 15s until dismissed."""
        import time as _time
        try:
            from user_manager import get_current_user as _gcu
            _raw = _gcu().get_name()
            _uname = _raw if _raw and _raw.lower() != "user" else ""
        except Exception:
            _uname = ""
        _hi = f"Hey {_uname}" if _uname else "Hey"
        phrases = [
            f"{_hi}, you asked me to remind you to {msg}.",
            f"{_hi}, just checking in. You wanted to {msg}.",
            f"{_hi}, still reminding you about {msg}. Say reminder off when you are ready.",
            f"{_hi}, do not forget. You set a reminder to {msg}.",
            f"{_hi}, your reminder is still active. You asked me to remind you to {msg}.",
        ]
        i = 0
        _time.sleep(15)
        while self._reminder_active.is_set() and not self._stop_event.is_set():
            if self.loop and not self.loop.is_closed():
                asyncio.run_coroutine_threadsafe(
                    self.agent.inject_agent_message(phrases[i % len(phrases)]), self.loop
                )
            i += 1
            _time.sleep(15)

    def _chime_loop_thread(self, wav_path: str):
        """Play a WAV file in a loop using sounddevice until _chime_stop_event is set."""
        import wave
        try:
            with wave.open(wav_path, 'rb') as wf:
                sr = wf.getframerate()
                channels = wf.getnchannels()
                sw = wf.getsampwidth()
                raw = wf.readframes(wf.getnframes())
            if sw == 2:
                audio = np.frombuffer(raw, dtype=np.int16)
            elif sw == 1:
                audio = ((np.frombuffer(raw, dtype=np.uint8).astype(np.int16)) - 128) * 256
            else:
                logger.warning(f"[CHIME] Unsupported sample width: {sw}")
                return
            if channels > 1:
                audio = audio.reshape(-1, channels)
            with sd.OutputStream(samplerate=sr, channels=channels, dtype='int16') as stream:
                while not self._chime_stop_event.is_set():
                    stream.write(audio)
        except Exception as e:
            logger.warning(f"[CHIME] Playback error: {e}")

    def run(self):
        """Run the agent in the background thread."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # Start background alarm/reminder checker
        alarm_thread = threading.Thread(target=self._alarm_checker_thread, daemon=True)
        alarm_thread.start()

        # Start proactive health check-in threads
        try:
            from health_checkin import HealthCheckinManager
            self._health_checkin = HealthCheckinManager(self)
            self._health_checkin.start()
            logger.info("[HEALTH] Proactive health check-in manager started")
        except Exception as e:
            logger.warning(f"[HEALTH] Could not start health check-in manager: {e}")

        # Wire motion detector → agent inject
        try:
            from motion import attach_agent as _attach_motion
            _attach_motion(self)
            logger.info("[MOTION] Motion detector wired to agent")
        except Exception as e:
            logger.warning(f"[MOTION] Could not attach motion detector: {e}")

        try:
            self.loop.run_until_complete(self.agent.run())
        except Exception as e:
            logger.error(f"Agent thread error: {e}")
        finally:
            self.loop.close()

    def stop(self):
        """Stop the agent."""
        self._chime_stop_event.set()   # stop any looping chime before teardown
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

    def _stop_alarm_handler():
        agent._alarm_active.clear()
        agent._chime_stop_event.set()
        return "Alarm stopped."

    agent.register_function(
        name="stop_alarm",
        description="Stop a currently ringing alarm chime",
        parameters={"type": "object", "properties": {}},
        handler=_stop_alarm_handler,
        client_side=True,
    )

    def _stop_reminder_handler():
        agent._reminder_active.clear()
        agent._current_reminder_msg = ""
        agent._chime_stop_event.set()
        return "Reminder dismissed."

    agent.register_function(
        name="stop_reminder",
        description="Dismiss a currently ringing reminder chime",
        parameters={"type": "object", "properties": {}},
        handler=_stop_reminder_handler,
        client_side=True,
    )

    from health_analysis import (
        log_sleep, log_water, log_mood, log_symptom, log_exercise,
        log_medication_taken, add_medication, add_health_condition,
        set_health_emergency_contact, get_health_summary, get_wellness_score,
    )
    from health_news import get_health_news, get_health_news_by_topic
    from emergency import trigger_emergency, cancel_emergency, set_doctor_contact
    import threading as _threading
    from pathlib import Path as _Path

    agent.register_function(
        name="log_sleep",
        description="Log how many hours the user slept last night, and optional quality (good/fair/poor)",
        parameters={
            "type": "object",
            "properties": {
                "hours": {"type": "number", "description": "Hours of sleep"},
                "quality": {"type": "string", "description": "Sleep quality: good, fair, or poor"},
            },
            "required": ["hours"],
        },
        handler=lambda hours, quality="fair": log_sleep(hours, quality),
        client_side=True,
    )

    agent.register_function(
        name="log_water",
        description="Log glasses of water the user has drunk",
        parameters={
            "type": "object",
            "properties": {
                "glasses": {"type": "integer", "description": "Number of glasses drunk"},
            },
            "required": ["glasses"],
        },
        handler=lambda glasses=1: log_water(glasses),
        client_side=True,
    )

    agent.register_function(
        name="log_mood",
        description="Log the user's current mood or emotional state",
        parameters={
            "type": "object",
            "properties": {
                "mood": {"type": "string", "description": "Mood description e.g. happy, anxious, tired"},
                "score": {"type": "integer", "description": "Optional mood score 1-10"},
            },
            "required": ["mood"],
        },
        handler=lambda mood, score=None: log_mood(mood, score),
        client_side=True,
    )

    agent.register_function(
        name="log_symptom",
        description="Log a health symptom the user is experiencing",
        parameters={
            "type": "object",
            "properties": {
                "symptom": {"type": "string", "description": "Symptom description e.g. headache, nausea"},
                "severity": {"type": "integer", "description": "Severity 1-10 (optional)"},
            },
            "required": ["symptom"],
        },
        handler=lambda symptom, severity=5: log_symptom(symptom, severity),
        client_side=True,
    )

    agent.register_function(
        name="log_exercise",
        description="Log a physical activity the user completed",
        parameters={
            "type": "object",
            "properties": {
                "activity": {"type": "string", "description": "Activity name e.g. running, yoga, walking"},
                "duration_minutes": {"type": "integer", "description": "Duration in minutes"},
            },
            "required": ["activity", "duration_minutes"],
        },
        handler=lambda activity, duration_minutes: log_exercise(activity, duration_minutes),
        client_side=True,
    )

    agent.register_function(
        name="log_medication_taken",
        description="Mark a medication as taken for today",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Medication name"},
            },
            "required": ["name"],
        },
        handler=lambda name: log_medication_taken(name),
        client_side=True,
    )

    agent.register_function(
        name="add_medication",
        description="Add a medication to the user's health profile with dosage and schedule",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Medication name"},
                "dosage": {"type": "string", "description": "Dosage e.g. 500mg (optional)"},
                "times": {"type": "string", "description": "When to take: morning, afternoon, evening, night, bedtime"},
            },
            "required": ["name"],
        },
        handler=lambda name, dosage="", times="morning": add_medication(name, dosage, times),
        client_side=True,
    )

    agent.register_function(
        name="add_health_condition",
        description="Add a medical condition to the user's health profile",
        parameters={
            "type": "object",
            "properties": {
                "condition": {"type": "string", "description": "Medical condition e.g. diabetes, hypertension"},
            },
            "required": ["condition"],
        },
        handler=lambda condition: add_health_condition(condition),
        client_side=True,
    )

    agent.register_function(
        name="set_health_emergency_contact",
        description="Save an emergency contact phone number in international format",
        parameters={
            "type": "object",
            "properties": {
                "phone_number": {"type": "string", "description": "Phone number in international format e.g. +2348012345678"},
            },
            "required": ["phone_number"],
        },
        handler=lambda phone_number: set_health_emergency_contact(phone_number),
        client_side=True,
    )

    agent.register_function(
        name="get_health_summary",
        description="Get a spoken health summary covering sleep, hydration, mood, exercise, and medications for today",
        parameters={"type": "object", "properties": {}},
        handler=lambda: get_health_summary(),
        client_side=True,
    )

    agent.register_function(
        name="get_wellness_score",
        description="Calculate and return the user's wellness score out of 100 based on recent health data",
        parameters={"type": "object", "properties": {}},
        handler=lambda: get_wellness_score(),
        client_side=True,
    )

    agent.register_function(
        name="get_health_news",
        description="Fetch the latest health news headlines. Optional topic filter like 'cancer', 'diabetes', 'heart disease'.",
        parameters={
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Optional health topic to filter news (e.g. cancer, diabetes, mental health)"},
                "count": {"type": "integer", "description": "Number of headlines to return, default 3"},
            },
        },
        handler=lambda topic=None, count=3: get_health_news(topic=topic, count=count),
        client_side=True,
    )

    agent.register_function(
        name="get_health_news_by_topic",
        description="Search health news for a specific topic like 'diabetes', 'cancer', 'heart disease', 'mental health'",
        parameters={
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "The health topic to search for"},
            },
            "required": ["topic"],
        },
        handler=lambda topic: get_health_news_by_topic(topic),
        client_side=True,
    )

    # --- Emergency functions ---
    def _trigger_emergency_handler():
        # Start the emergency alarm chime
        emergency_wav = str(_Path(__file__).parent / "alarm.wav")
        agent._alarm_active.set()
        agent._chime_stop_event.set()
        import time as _t; _t.sleep(0.05)
        agent._chime_stop_event.clear()
        _threading.Thread(
            target=agent._chime_loop_thread,
            args=(emergency_wav,),
            daemon=True,
        ).start()
        return trigger_emergency(agent_thread=agent)

    def _cancel_emergency_handler():
        agent._alarm_active.clear()
        agent._chime_stop_event.set()
        return cancel_emergency()

    agent.register_function(
        name="trigger_emergency",
        description="Trigger an emergency SOS alert — sends Telegram message, starts alarm, repeats every 5 minutes",
        parameters={"type": "object", "properties": {}},
        handler=_trigger_emergency_handler,
        client_side=True,
    )

    agent.register_function(
        name="cancel_emergency",
        description="Cancel an active emergency alert and stop the alarm",
        parameters={"type": "object", "properties": {}},
        handler=_cancel_emergency_handler,
        client_side=True,
    )

    agent.register_function(
        name="set_doctor_contact",
        description="Save the user's doctor phone number in international format",
        parameters={
            "type": "object",
            "properties": {
                "number": {"type": "string", "description": "Doctor's phone number in international format"},
            },
            "required": ["number"],
        },
        handler=lambda number: set_doctor_contact(number),
        client_side=True,
    )

    # --- Telegram voice functions ---
    from telegram_service import (
        send_voice_message as _tg_send,
        send_health_report_telegram as _tg_health_report,
        check_telegram_status as _tg_status,
    )

    agent.register_function(
        name="send_telegram_message",
        description="Send a custom text message to the user's Telegram contact",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Message text to send via Telegram"},
            },
            "required": ["text"],
        },
        handler=lambda text: _tg_send(text),
        client_side=True,
    )

    agent.register_function(
        name="send_health_report_telegram",
        description="Generate and send the user's weekly health report via Telegram",
        parameters={"type": "object", "properties": {}},
        handler=lambda: _tg_health_report(),
        client_side=True,
    )

    agent.register_function(
        name="check_telegram_status",
        description="Check whether Telegram is configured and the bot is reachable",
        parameters={"type": "object", "properties": {}},
        handler=lambda: _tg_status(),
        client_side=True,
    )

    # --- Spotify voice functions ---
    from spotify_service import (
        play_music as _sp_play,
        play_artist_music as _sp_play_artist,
        pause_music as _sp_pause,
        resume_music as _sp_resume,
        next_track as _sp_next,
        previous_track as _sp_prev,
        set_volume as _sp_volume,
        get_now_playing as _sp_now_playing,
    )

    agent.register_function(
        name="play_spotify",
        description="Play a song or playlist by name on Spotify",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Song name, playlist name, or search query"},
            },
            "required": ["query"],
        },
        handler=lambda query: _sp_play(query),
        client_side=True,
    )

    agent.register_function(
        name="play_spotify_artist",
        description="Play music by a specific artist on Spotify",
        parameters={
            "type": "object",
            "properties": {
                "artist": {"type": "string", "description": "Artist name"},
            },
            "required": ["artist"],
        },
        handler=lambda artist: _sp_play_artist(artist),
        client_side=True,
    )

    agent.register_function(
        name="pause_spotify",
        description="Pause Spotify playback",
        parameters={"type": "object", "properties": {}},
        handler=lambda: _sp_pause(),
        client_side=True,
    )

    agent.register_function(
        name="resume_spotify",
        description="Resume Spotify playback",
        parameters={"type": "object", "properties": {}},
        handler=lambda: _sp_resume(),
        client_side=True,
    )

    agent.register_function(
        name="skip_track",
        description="Skip to the next track on Spotify",
        parameters={"type": "object", "properties": {}},
        handler=lambda: _sp_next(),
        client_side=True,
    )

    agent.register_function(
        name="previous_track",
        description="Go back to the previous track on Spotify",
        parameters={"type": "object", "properties": {}},
        handler=lambda: _sp_prev(),
        client_side=True,
    )

    agent.register_function(
        name="set_spotify_volume",
        description="Set Spotify playback volume from 0 to 100",
        parameters={
            "type": "object",
            "properties": {
                "percent": {"type": "integer", "description": "Volume level 0-100"},
            },
            "required": ["percent"],
        },
        handler=lambda percent: _sp_volume(percent),
        client_side=True,
    )

    agent.register_function(
        name="get_now_playing",
        description="Get the currently playing song on Spotify",
        parameters={"type": "object", "properties": {}},
        handler=lambda: _sp_now_playing(),
        client_side=True,
    )

    from motion import (
        start_motion_monitoring as _motion_start,
        stop_motion_monitoring as _motion_stop,
        get_motion_status as _motion_status,
        set_motion_cooldown as _motion_cooldown,
    )

    agent.register_function(
        name="start_motion_monitoring",
        description="Start background motion monitoring via PIR sensor (Raspberry Pi) or webcam",
        parameters={"type": "object", "properties": {}},
        handler=lambda: _motion_start(),
        client_side=True,
    )

    agent.register_function(
        name="stop_motion_monitoring",
        description="Stop background motion monitoring",
        parameters={"type": "object", "properties": {}},
        handler=lambda: _motion_stop(),
        client_side=True,
    )

    agent.register_function(
        name="get_motion_status",
        description="Get the current motion monitoring status, backend type, and last detection time",
        parameters={"type": "object", "properties": {}},
        handler=lambda: _motion_status(),
        client_side=True,
    )

    agent.register_function(
        name="set_motion_cooldown",
        description="Set how many seconds must pass between motion alerts to avoid repeated triggers",
        parameters={
            "type": "object",
            "properties": {
                "seconds": {"type": "integer", "description": "Cooldown in seconds (e.g. 30)"},
            },
            "required": ["seconds"],
        },
        handler=lambda seconds: _motion_cooldown(seconds),
        client_side=True,
    )

    from weather import get_weather_forecast

    agent.register_function(
        name="get_weather_forecast",
        description="Get weather forecast for a future date (tomorrow, day after tomorrow, etc.)",
        parameters={
            "type": "object",
            "properties": {
                "days_ahead": {
                    "type": "integer",
                    "description": "Number of days ahead: 1=tomorrow, 2=day after tomorrow, up to 5",
                },
            },
            "required": ["days_ahead"],
        },
        handler=lambda days_ahead: get_weather_forecast(
            get_current_user().data.get("location", "Lagos"), int(days_ahead)
        ),
        client_side=True,
    )

    return agent
