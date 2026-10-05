"""Background wake word detector using Vosk (offline, no API key)."""

import json
import queue
import threading
import time

import sounddevice as sd
from vosk import Model, KaldiRecognizer

WAKE_WORDS = ["jarvis", "hey jarvis"]
SAMPLE_RATE = 16000
MODEL_PATH = "models/vosk-small"


class WakeWordListener:
    """Listens continuously in a background thread for the wake word."""

    def __init__(self, on_wake=None, device=None):
        self.model = Model(MODEL_PATH)
        self.recognizer = KaldiRecognizer(self.model, SAMPLE_RATE)
        self.recognizer.SetWords(True)
        

        self.on_wake = on_wake
        self.device = device
        self.audio_queue = queue.Queue()
        self.running = False
        self.thread = None

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            print(f"[mic warning] {status}")
        self.audio_queue.put(bytes(indata))

    def _listen_loop(self):
        with sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=8000,
            device=self.device,
            dtype="int16",
            channels=1,
            callback=self._audio_callback,
        ):
            print("[wake] Listening for 'Jarvis'... (say the wake word)")
            while self.running:
                try:
                    data = self.audio_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                if self.recognizer.AcceptWaveform(data):
                    result = json.loads(self.recognizer.Result())
                    text = result.get("text", "").lower().strip()
                    if text:
                        print(f"[wake heard] {text}")
                        if any(w in text for w in WAKE_WORDS):
                            print("[wake] Wake word detected!")
                            self.recognizer.Reset()
                            while not self.audio_queue.empty():
                                try:
                                    self.audio_queue.get_nowait()
                                except queue.Empty:
                                    break
                            if self.on_wake:
                                self.on_wake()
                            time.sleep(0.3)

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        print("[wake] Listener stopped.")