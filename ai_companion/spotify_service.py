import os
from dotenv import load_dotenv

load_dotenv()

try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    SPOTIFY_AVAILABLE = True
except ImportError:
    SPOTIFY_AVAILABLE = False

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI")

sp = None
if SPOTIFY_AVAILABLE:
    scope = "user-read-playback-state user-modify-playback-state"
    sp = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            redirect_uri=REDIRECT_URI,
            scope=scope,
            open_browser=True,
        )
    )


def get_device(device_name=None):
    if not SPOTIFY_AVAILABLE or sp is None:
        return None
    devices = sp.devices()["devices"]

    if not devices:
        return None

    if device_name:
        for d in devices:
            if device_name.lower() in d["name"].lower():
                return d["id"]

    return devices[0]["id"]


def play_song(query, device=None):
    if not SPOTIFY_AVAILABLE or sp is None:
        raise RuntimeError("Spotify not available")
    results = sp.search(q=query, type="track", limit=1)

    if not results["tracks"]["items"]:
        return False

    track_uri = results["tracks"]["items"][0]["uri"]

    device_id = get_device(device)

    sp.start_playback(device_id=device_id, uris=[track_uri])

    return True


def play_playlist(query, device=None):
    if not SPOTIFY_AVAILABLE or sp is None:
        raise RuntimeError("Spotify not available")
    results = sp.search(q=query, type="playlist", limit=1)

    if not results["playlists"]["items"]:
        return False

    playlist_uri = results["playlists"]["items"][0]["uri"]

    device_id = get_device(device)

    sp.start_playback(device_id=device_id, context_uri=playlist_uri)

    return True


def play_artist(query, device=None):
    if not SPOTIFY_AVAILABLE or sp is None:
        raise RuntimeError("Spotify not available")
    results = sp.search(q=query, type="artist", limit=1)

    if not results["artists"]["items"]:
        return False

    artist_uri = results["artists"]["items"][0]["uri"]

    device_id = get_device(device)

    sp.start_playback(device_id=device_id, context_uri=artist_uri)

    return True


def play_music(device=None):
    if not SPOTIFY_AVAILABLE or sp is None:
        raise RuntimeError("Spotify not available")
    # fallback playlist (Top Hits)
    playlist = "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"
    device_id = get_device(device)
    sp.start_playback(device_id=device_id, context_uri=playlist)


def pause_music():
    """Pause the current playback"""
    if not SPOTIFY_AVAILABLE or sp is None:
        raise RuntimeError("Spotify not available")

    try:
        sp.pause_playback()
        return True
    except Exception:
        return False


def resume_music():
    """Resume playback"""
    if not SPOTIFY_AVAILABLE or sp is None:
        return False
    try:
        sp.start_playback()
        return True
    except Exception:
        return False


def next_track():
    """Skip to next track"""
    if not SPOTIFY_AVAILABLE or sp is None:
        return False
    try:
        sp.next_track()
        return True
    except Exception:
        return False


def previous_track():
    """Go back to previous track"""
    if not SPOTIFY_AVAILABLE or sp is None:
        return False
    try:
        sp.previous_track()
        return True
    except Exception:
        return False
