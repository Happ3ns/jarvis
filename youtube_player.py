"""YouTube audio playback — no account, no Premium, no API key."""

import subprocess
import threading

_current_proc = None
_lock = threading.Lock()


def _stop_spotify_playback():
    """Pause Spotify if anything is playing there."""
    try:
        from tools import get_spotify_client
        sp = get_spotify_client()
        if sp is not None:
            sp.pause_playback()
    except Exception:
        pass


def play_on_youtube(query: str) -> str:
    """Search YouTube and play the first result's audio through mpv."""
    global _current_proc

    with _lock:
        # Stop any current playback
        if _current_proc is not None:
            try:
                _current_proc.terminate()
                _current_proc.wait(timeout=2)
            except Exception:
                pass
            _current_proc = None

        # Pause Spotify so they don't overlap
        _stop_spotify_playback()

        # Search YouTube
        try:
            result = subprocess.run(
                ["yt-dlp", f"ytsearch1:{query}", "--get-title", "--get-id",
                 "--no-playlist", "--quiet", "--js-runtimes", "deno"],
                capture_output=True, text=True, timeout=30,
            )
            lines = [l for l in result.stdout.strip().split("\n") if l]
            if len(lines) < 2:
                return f"Couldn't find {query} on YouTube."
            title, video_id = lines[0], lines[1]
        except FileNotFoundError:
            return "Install yt-dlp first: pip install yt-dlp"
        except subprocess.TimeoutExpired:
            return "YouTube search timed out."
        except Exception as e:
            return f"YouTube search error: {e}"

        # Play with mpv
        url = f"https://www.youtube.com/watch?v={video_id}"
        print(f"[YouTube] Playing: {title}")
        try:
            _current_proc = subprocess.Popen(
                ["mpv", "--no-video", "--really-quiet", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            return "Install mpv first. Run: winget install mpv-player.mpv-CI.MSVC --exact"

        return f"Playing {title} on YouTube."


def stop_youtube() -> str:
    """Stop whatever's currently playing."""
    global _current_proc
    with _lock:
        if _current_proc is None:
            return "Nothing is playing."
        try:
            _current_proc.terminate()
            _current_proc = None
            return "Stopped."
        except Exception as e:
            return f"Error stopping: {e}"