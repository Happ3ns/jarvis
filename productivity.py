"""Productivity tools — email, screenshot, file search, clipboard."""

import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path


# ---------- Email ----------

def get_email_credentials():
    email = os.environ.get("JARVIS_EMAIL")
    password = os.environ.get("JARVIS_EMAIL_PASS")
    name = os.environ.get("JARVIS_EMAIL_NAME", "Akshat")
    return email, password, name


def send_email(to: str, subject: str, body: str) -> str:
    """Send an email via Gmail SMTP."""
    sender, password, name = get_email_credentials()

    if not sender or not password:
        return ("Email isn't configured. Set JARVIS_EMAIL and "
                "JARVIS_EMAIL_PASS environment variables.")

    try:
        msg = MIMEMultipart()
        msg["From"] = f"{name} <{sender}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.send_message(msg)

        return f"Email sent to {to}."
    except smtplib.SMTPAuthenticationError:
        return "Gmail rejected the login. Check your App Password."
    except Exception as e:
        return f"Email error: {e}"


# ---------- Screenshot ----------

def take_screenshot(save_dir: str = "screenshots") -> str:
    """Capture the full screen and save it."""
    try:
        import pyautogui
        folder = Path(save_dir)
        folder.mkdir(exist_ok=True)
        filename = folder / f"shot_{datetime.now():%Y%m%d_%H%M%S}.png"
        img = pyautogui.screenshot()
        img.save(filename)
        return f"Screenshot saved to {filename}."
    except ImportError:
        return "Install pyautogui for screenshots: pip install pyautogui"
    except Exception as e:
        return f"Screenshot error: {e}"


# ---------- File search ----------

def find_file(name: str, search_dir: str = None, max_results: int = 5) -> str:
    """Search for files matching a name in the user's home folder."""
    if search_dir is None:
        search_dir = str(Path.home())

    name_lower = name.lower()
    matches = []
    skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv",
                 "AppData", ".cache", "Library"}

    try:
        for root, dirs, files in os.walk(search_dir):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for f in files:
                if name_lower in f.lower():
                    matches.append(os.path.join(root, f))
                    if len(matches) >= max_results:
                        raise StopIteration
    except StopIteration:
        pass
    except Exception as e:
        return f"Search error: {e}"

    if not matches:
        return f"No files matching '{name}' found."

    lines = "\n".join(f"  {m}" for m in matches)
    return f"Found {len(matches)} file(s):\n{lines}"


def open_file(path: str) -> str:
    """Open a file or folder with the default Windows app."""
    p = Path(path)
    if not p.exists():
        return f"Path not found: {path}"
    try:
        os.startfile(str(p))
        return f"Opening {p.name}."
    except Exception as e:
        return f"Couldn't open: {e}"


# ---------- Clipboard ----------

def get_clipboard() -> str:
    """Read the current clipboard contents."""
    try:
        import pyperclip
        text = pyperclip.paste()
        if not text:
            return "Clipboard is empty."
        if len(text) > 200:
            text = text[:200] + "..."
        return f"Clipboard: {text}"
    except ImportError:
        return "Install pyperclip: pip install pyperclip"
    except Exception as e:
        return f"Clipboard error: {e}"


def set_clipboard(text: str) -> str:
    """Copy text to the clipboard."""
    try:
        import pyperclip
        pyperclip.copy(text)
        return "Copied to clipboard."
    except ImportError:
        return "Install pyperclip: pip install pyperclip"
    except Exception as e:
        return f"Clipboard error: {e}"


# ---------- Morning briefing ----------

def morning_briefing() -> str:
    """Combine weather, date, and system info into a daily briefing."""
    from tools import get_weather, get_time, get_date

    parts = []
    parts.append(get_date())
    parts.append(get_time())
    parts.append(get_weather("Kanpur"))

    try:
        import psutil
        battery = psutil.sensors_battery()
        if battery and not battery.power_plugged:
            parts.append(f"Battery at {int(battery.percent)}%")
    except Exception:
        pass

    return ". ".join(parts) + "."