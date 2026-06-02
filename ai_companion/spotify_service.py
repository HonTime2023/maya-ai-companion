"""
Spotify Service — Voice-callable Spotify playback control for JARVIS.
All public functions return plain spoken strings.
Gracefully handles missing credentials or unavailable Spotify.
"""
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

logger = logging.getLogger("AI_Companion")

# Store OAuth cache next to this file so it's found regardless of cwd
_CACHE_PATH = str(Path(__file__).parent / ".spotify_token_cache")

try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    _SPOTIPY_AVAILABLE = True
except ImportError:
    _SPOTIPY_AVAILABLE = False

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback")

# Lazy singleton — only created on first use
_sp = None
SPOTIFY_AVAILABLE = False


def _get_sp():
    """Return authenticated Spotify client, or None if unavailable."""
    global _sp, SPOTIFY_AVAILABLE
    if _sp is not None:
        return _sp
    if not _SPOTIPY_AVAILABLE or not CLIENT_ID or not CLIENT_SECRET:
        return None
    try:
        scope = (
            "user-read-playback-state "
            "user-modify-playback-state "
            "user-read-currently-playing"
        )
        _sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
                redirect_uri=REDIRECT_URI,
                scope=scope,
                cache_path=_CACHE_PATH,
                open_browser=True,
            )
        )
        SPOTIFY_AVAILABLE = True
        return _sp
    except Exception as e:
        logger.warning(f"[SPOTIFY] Init failed: {e}")
        return None


def _not_available() -> str:
    if not _SPOTIPY_AVAILABLE:
        return "The spotipy library is not installed. Run pip install spotipy to enable Spotify."
    if not CLIENT_ID or not CLIENT_SECRET:
        return "Spotify is not configured. Please add SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET to your .env file."
    return "Spotify is not available right now."


def _get_device_id(device_name=None):
    sp = _get_sp()
    if sp is None:
        return None
    try:
        devices = sp.devices().get("devices", [])
        if devices:
            names = [d["name"] for d in devices]
            logger.info(f"[SPOTIFY] Available devices: {names}")
        else:
            logger.warning("[SPOTIFY] No devices returned from Spotify API")
            return None
        if device_name:
            for d in devices:
                if device_name.lower() in d["name"].lower():
                    return d["id"]
        # Prefer active device, otherwise use first available
        for d in devices:
            if d.get("is_active"):
                return d["id"]
        return devices[0]["id"]
    except Exception as e:
        logger.error(f"[SPOTIFY] device detection error: {e}")
        return None


# ------------------------------------------------------------------ #
# Voice-callable playback functions
# ------------------------------------------------------------------ #

def play_music(query: str) -> str:
    """
    Play a song, artist, or playlist by name.
    Tries tracks first, then playlists.
    """
    sp = _get_sp()
    if sp is None:
        return _not_available()

    try:
        # Search first (doesn't need a device)
        results = sp.search(q=query, type="track", limit=1)
        tracks = results.get("tracks", {}).get("items", [])

        playlist_fallback = None
        if not tracks:
            results = sp.search(q=query, type="playlist", limit=1)
            items = results.get("playlists", {}).get("items", [])
            if items:
                playlist_fallback = items[0]

        if not tracks and not playlist_fallback:
            return f"I could not find anything on Spotify matching '{query}'."

        device_id = _get_device_id()
        if device_id is None:
            return (
                "I found the song but Spotify has no active device. "
                "Please open Spotify on your phone or PC, press play on any song for a moment, "
                "then ask me again."
            )

        def _try_play(fn):
            """Try playback, if 403/not-active try transfer first then retry."""
            try:
                fn()
                return True
            except Exception as e1:
                logger.warning(f"[SPOTIFY] first play attempt failed ({e1}), trying transfer")
                try:
                    import time
                    sp.transfer_playback(device_id=device_id, force_play=False)
                    time.sleep(0.8)
                    fn()
                    return True
                except Exception as e2:
                    logger.error(f"[SPOTIFY] play after transfer failed: {e2}")
                    return False

        if tracks:
            track = tracks[0]
            name = track["name"]
            artist = track["artists"][0]["name"]
            uri = track["uri"]
            ok = _try_play(lambda: sp.start_playback(device_id=device_id, uris=[uri]))
            if ok:
                return f"Now playing {name} by {artist}."
            return f"I found {name} by {artist} but could not start playback. Try pressing play in Spotify manually first."

        pl = playlist_fallback
        ok = _try_play(lambda: sp.start_playback(device_id=device_id, context_uri=pl["uri"]))
        if ok:
            return f"Now playing playlist: {pl['name']}."
        return f"I found the playlist {pl['name']} but could not start playback."

    except Exception as e:
        logger.error(f"[SPOTIFY] play_music error: {e}")
        return "I ran into an issue playing that on Spotify. Make sure Spotify is open on a device."


def play_artist_music(artist: str) -> str:
    """Play music by a specific artist."""
    sp = _get_sp()
    if sp is None:
        return _not_available()
    try:
        device_id = _get_device_id()
        if device_id is None:
            return "No active Spotify device found. Open Spotify and press play briefly, then try again."
        results = sp.search(q=artist, type="artist", limit=1)
        artists = results.get("artists", {}).get("items", [])
        if not artists:
            return f"I could not find the artist {artist} on Spotify."
        a = artists[0]
        sp.start_playback(device_id=device_id, context_uri=a["uri"])
        return f"Now playing music by {a['name']}."
    except Exception as e:
        logger.error(f"[SPOTIFY] play_artist error: {e}")
        return f"I could not play {artist} right now."


def pause_music() -> str:
    """Pause Spotify playback."""
    sp = _get_sp()
    if sp is None:
        return _not_available()
    try:
        sp.pause_playback()
        return "Music paused."
    except Exception:
        return "I could not pause the music. Spotify may not be playing anything."


def resume_music() -> str:
    """Resume Spotify playback."""
    sp = _get_sp()
    if sp is None:
        return _not_available()
    try:
        sp.start_playback()
        return "Music resumed."
    except Exception:
        return "I could not resume the music."


def next_track() -> str:
    """Skip to the next track."""
    sp = _get_sp()
    if sp is None:
        return _not_available()
    try:
        sp.next_track()
        return "Skipping to the next track."
    except Exception:
        return "I could not skip the track right now."


def previous_track() -> str:
    """Go back to the previous track."""
    sp = _get_sp()
    if sp is None:
        return _not_available()
    try:
        sp.previous_track()
        return "Going back to the previous track."
    except Exception:
        return "I could not go back to the previous track."


def set_volume(percent: int) -> str:
    """Set Spotify playback volume (0-100)."""
    sp = _get_sp()
    if sp is None:
        return _not_available()
    try:
        percent = max(0, min(100, int(percent)))
        device_id = _get_device_id()
        sp.volume(percent, device_id=device_id)
        return f"Volume set to {percent} percent."
    except Exception:
        return "I could not change the volume right now."


def get_now_playing() -> str:
    """Return what is currently playing on Spotify."""
    sp = _get_sp()
    if sp is None:
        return _not_available()
    try:
        current = sp.current_playback()
        if current is None or not current.get("is_playing"):
            return "Nothing is currently playing on Spotify."
        item = current.get("item")
        if item:
            name = item["name"]
            artist = item["artists"][0]["name"]
            return f"Currently playing {name} by {artist}."
        return "Something is playing on Spotify but I could not get the track details."
    except Exception:
        return "I could not check what is playing on Spotify right now."


# ---------------------------------------------------------------------------
# Legacy compatibility aliases (used by old main.py pipeline)
# ---------------------------------------------------------------------------
def play_song(query: str, device=None) -> bool:
    """Legacy wrapper — returns True/False for old pipeline."""
    result = play_music(query)
    return not result.startswith("I could not") and not result.startswith("No active")


def play_artist(query: str, device=None) -> bool:
    """Legacy wrapper."""
    result = play_artist_music(query)
    return not result.startswith("I could not") and not result.startswith("No active")
