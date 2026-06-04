"""
JARVIS Web App — FastAPI WebSocket Proxy Server
Bridges browser audio <-> Deepgram Voice Agent.
Executes all function calls server-side (API keys never reach the browser).

Run from project root:
  cd AI_Companion
  cleanenv/Scripts/python.exe -m uvicorn webapp.server:app --host 0.0.0.0 --port 8000 --reload

Or directly:
  python webapp/server.py
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# ── path setup ────────────────────────────────────────────────────────────────
AI_DIR = Path(__file__).parent.parent / "ai_companion"
sys.path.insert(0, str(AI_DIR))

from dotenv import load_dotenv
load_dotenv(AI_DIR / ".env")

import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from function_map import run_function, build_settings_config
from pydantic import BaseModel
import urllib.request
import urllib.parse

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger("JARVIS-Web")

app = FastAPI(title="JARVIS Web")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── /health ───────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok"}


# ── /function — REST endpoint for direct UI function calls (Spotify controls etc.)
class FnRequest(BaseModel):
    name: str
    args: dict = {}
    function_call_id: str = ""

@app.post("/function")
async def call_function(req: FnRequest):
    try:
        result = run_function(req.name, req.args)
        return result
    except Exception as exc:
        return {"result": str(exc), "ui_type": "none", "ui_data": {}}


# ── /lyrics — fetch lyrics for currently playing (or given) track ─────────────
@app.get("/lyrics")
async def get_lyrics(artist: str = "", title: str = ""):
    """
    Multi-source lyrics lookup.  Returns lrc_lines (timestamps) when available
    so the frontend can advance the glow in sync with the song.
    """
    loop = asyncio.get_event_loop()
    try:
        # Resolve track from Spotify if not supplied
        if not artist or not title:
            from spotify_service import get_now_playing_structured
            info = await loop.run_in_executor(None, get_now_playing_structured)
            if not info.get("is_playing"):
                return JSONResponse({"found": False, "reason": "nothing_playing"})
            artist = info["artist"]
            title  = info["track"]

        track_clean  = title.strip()
        artist_clean = artist.strip()
        query        = f"{track_clean} {artist_clean}"

        def _parse_lrc(raw: str):
            """Parse LRC into [{ms, text}] sorted by time. Returns None if no timestamps found."""
            import re as _re
            pat = _re.compile(r'\[(\d{2}):(\d{2})[.:](\d{2,3})\](.*)')
            # Purely-instrumental marker characters — skip these as lyric lines
            _instrumental = _re.compile(r'^[♪♫~🎵🎶\-\s]+$')
            lines = []
            for line in raw.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
                m = pat.match(line.strip())
                if m:
                    mins, secs, cs, text = m.groups()
                    ms   = int(mins)*60000 + int(secs)*1000 + int(cs.ljust(3,'0'))
                    text = text.strip()
                    # Skip empty lines and pure instrumental markers
                    if text and not _instrumental.match(text):
                        lines.append({"ms": ms, "text": text})
            return lines if lines else None

        def _fetch_syncedlyrics():
            """Returns (plain_text, lrc_lines_or_None)."""
            try:
                import syncedlyrics, re as _re
                # Try plain text first
                plain = syncedlyrics.search(query, plain_only=True)
                if plain and plain.strip():
                    return plain.strip(), None
                # Try synced/LRC — parse timestamps for real-time glow
                synced = syncedlyrics.search(query)
                if synced:
                    lrc_lines = _parse_lrc(synced)
                    if lrc_lines:
                        plain_text = '\n'.join(l['text'] for l in lrc_lines)
                        return plain_text, lrc_lines
                    # No parseable timestamps — strip and return plain
                    clean = _re.sub(r'\[\d{2}:\d{2}[.:]\d{2,3}\]', '', synced)
                    clean = _re.sub(r'\[(?!feat|ft)[^\]]*\]', '', clean)
                    clean = _re.sub(r'\n{3,}', '\n\n', clean.strip())
                    return clean, None
            except Exception as e:
                log.warning(f"syncedlyrics failed: {e}")
            return None, None

        def _fetch_ovh():
            """Fallback: lyrics.ovh (plain text only)."""
            try:
                safe_a = urllib.parse.quote(artist_clean, safe="")
                safe_t = urllib.parse.quote(track_clean,  safe="")
                url    = f"https://api.lyrics.ovh/v1/{safe_a}/{safe_t}"
                req2   = urllib.request.Request(url, headers={"User-Agent": "JARVIS/1.0"})
                with urllib.request.urlopen(req2, timeout=8) as resp:
                    data = json.loads(resp.read().decode())
                    return data.get("lyrics") or None
            except Exception:
                return None

        def _find_lyrics():
            text, lrc = _fetch_syncedlyrics()
            if text:
                return text, lrc
            ovh = _fetch_ovh()
            return ovh, None

        # Also get playback position so frontend can offset LRC timestamps
        from spotify_service import get_now_playing_structured as _gnp
        sp_pos = await loop.run_in_executor(None, _gnp)
        progress_ms = sp_pos.get("progress_ms", 0) if sp_pos.get("is_playing") else 0

        lyrics_text, lrc_lines = await loop.run_in_executor(None, _find_lyrics)
        if not lyrics_text:
            return JSONResponse({"found": False, "track": title, "artist": artist,
                                 "reason": "not_found"})
        return JSONResponse({
            "found":       True,
            "track":       title,
            "artist":      artist,
            "lyrics":      lyrics_text,
            "lrc_lines":   lrc_lines,    # [{ms, text}] or null
            "progress_ms": progress_ms,  # current playback position at time of fetch
        })
    except Exception as exc:
        log.error(f"/lyrics error: {exc}")
        return JSONResponse({"found": False, "reason": str(exc)})

# ── /ws  — voice proxy ────────────────────────────────────────────────────────
@app.websocket("/ws")
async def voice_proxy(browser_ws: WebSocket):
    await browser_ws.accept()
    log.info("Browser connected")

    dg_key = os.getenv("DEEPGRAM_API_KEY")
    if not dg_key:
        await browser_ws.send_json({"type": "Error", "message": "DEEPGRAM_API_KEY not set"})
        await browser_ws.close()
        return

    dg_url = "wss://agent.deepgram.com/v1/agent/converse"

    try:
        async with websockets.connect(
            dg_url,
            additional_headers={"Authorization": f"Token {dg_key}"},
            ping_interval=None,
            max_size=10 * 1024 * 1024,
        ) as dg_ws:
            log.info("Connected to Deepgram Voice Agent")

            # Send full agent configuration
            config = build_settings_config()
            await dg_ws.send(json.dumps(config))
            log.info("Settings sent to Deepgram")

            stop_event = asyncio.Event()

            async def browser_to_deepgram():
                """Forward mic audio from browser → Deepgram."""
                try:
                    while not stop_event.is_set():
                        data = await browser_ws.receive_bytes()
                        await dg_ws.send(data)
                except (WebSocketDisconnect, Exception):
                    stop_event.set()

            async def deepgram_to_browser():
                """Forward Deepgram messages → browser, intercepting function calls."""
                try:
                    async for raw in dg_ws:
                        if stop_event.is_set():
                            break

                        if isinstance(raw, bytes):
                            # TTS audio — pass straight to browser
                            await browser_ws.send_bytes(raw)
                            continue

                        msg = json.loads(raw)
                        mtype = msg.get("type", "")

                        if mtype == "FunctionCallRequest":
                            # Deepgram sends: {"functions": [{"id":…,"name":…,"arguments":"{}"}]}
                            for func_call in msg.get("functions", []):
                                fname   = func_call.get("name", "")
                                func_id = func_call.get("id", "")
                                raw_args = func_call.get("arguments", "{}")
                                try:
                                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                                except Exception:
                                    args = {}
                                log.info(f"Function call: {fname}({args})")

                                # ── Step 1: Instantly show loading card in browser ──
                                await browser_ws.send_json({
                                    "type": "UICardLoading",
                                    "function_name": fname,
                                })

                                # ── Step 2: Execute function in thread pool (non-blocking) ──
                                try:
                                    loop = asyncio.get_running_loop()
                                    result = await loop.run_in_executor(
                                        None, run_function, fname, args
                                    )
                                except Exception as exc:
                                    log.error(f"Function {fname} error: {exc}")
                                    result = {"result": str(exc), "ui_type": "none", "ui_data": {}}

                                # ── Step 3: Send FunctionCallResponse + UICard simultaneously ──
                                # This means Deepgram starts generating speech at the exact same
                                # moment the browser receives the real card — no "card then silence".
                                await asyncio.gather(
                                    dg_ws.send(json.dumps({
                                        "type": "FunctionCallResponse",
                                        "name": fname,
                                        "id": func_id,
                                        "content": json.dumps(result["result"]),
                                    })),
                                    browser_ws.send_json({
                                        "type": "UICard",
                                        "function_name": fname,
                                        "ui_type": result.get("ui_type", "none"),
                                        "ui_data": result.get("ui_data", {}),
                                        "result_text": result["result"],
                                    }),
                                )

                        else:
                            # Forward everything else to browser as-is
                            await browser_ws.send_json(msg)

                except Exception as exc:
                    log.error(f"Deepgram→browser error: {exc}")
                    stop_event.set()

            await asyncio.gather(
                browser_to_deepgram(),
                deepgram_to_browser(),
            )

    except Exception as exc:
        log.error(f"Proxy error: {exc}")
        try:
            await browser_ws.send_json({"type": "Error", "message": str(exc)})
        except Exception:
            pass
    finally:
        log.info("Browser session ended")

# ── static files ──────────────────────────────────────────────────────────────
static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
