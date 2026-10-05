"""YouTube audio playback — no account, no Premium, no API key."""

import subprocess
import threading

_current_proc = None
_lock = threading.Lock()


def _stop_spotify_playback():
    try:
        from tools import get_spotify_client
        sp = get_spotify_client()
        if sp is not None:
            sp.pause_playback()
    except Exception:
        pass


def play_on_youtube(query: str) -> str:
    global _current_proc
    with _lock:
        if _current_proc is not None:
            try:
                _current_proc.terminate()
                _current_proc.wait(timeout=2)
            except Exception:
                pass
            _current_proc = None

        _stop_spotify_playback()

        try:
            result = subprocess.run(
                ["yt-dlp", f"ytsearch5:{query}", "--get-title", "--get-id",
                 "--no-playlist", "--quiet", "--js-runtimes", "deno"],
                capture_output=True, text=True, timeout=20,
            )
            lines = [l for l in result.stdout.strip().split("\n") if l]
            if len(lines) < 2:
                return f"Couldn't find {query} on YouTube."

            pairs = [(lines[i], lines[i + 1]) for i in range(0, len(lines) - 1, 2)]

            bad_words = ["cover", "remix", "karaoke", "instrumental",
                         "reaction", "tutorial", "live", "slowed",
                         "reverb", "8d", "bass boosted", "mashup"]
            good = [p for p in pairs
                    if not any(b in p[0].lower() for b in bad_words)]

            title, video_id = good[0] if good else pairs[0]

        except FileNotFoundError:
            return "Install yt-dlp first: pip install yt-dlp"
        except subprocess.TimeoutExpired:
            return "YouTube search timed out."
        except Exception as e:
            return f"YouTube search error: {e}"

        url = f"https://www.youtube.com/watch?v={video_id}"
        try:
            _current_proc = subprocess.Popen(
                ["mpv", "--no-video", "--really-quiet", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            return "Install mpv first: winget install mpv"

        return f"Playing {title} on YouTube."


def stop_youtube() -> str:
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