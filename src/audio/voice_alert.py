"""
Offline text-to-speech engine using pyttsx3, which works identically on:
  - macOS  (uses NSSpeechSynthesizer under the hood)
  - Raspberry Pi / Linux (uses espeak-ng under the hood — installed by
    scripts/setup_pi.sh via `apt install espeak-ng`)

No internet connection required, which matters for a mobility device used
outdoors.
"""

import logging
import queue
import threading

import pyttsx3

logger = logging.getLogger("smart_cane")


class VoiceEngine:
    """
    Runs TTS on its own dedicated thread with a queue, so speaking never
    blocks the vision/sensor loops, and phrases are spoken one at a time
    in order (never overlapping/garbled).
    """

    def __init__(self, rate: int = 175, volume: float = 1.0, voice_id: str = None):
        self.rate = rate
        self.volume = volume
        self.voice_id = voice_id

        self._queue = queue.Queue()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._speak_loop, daemon=True)
        self._thread.start()

    def _init_engine(self):
        engine = pyttsx3.init()
        engine.setProperty("rate", self.rate)
        engine.setProperty("volume", self.volume)
        if self.voice_id:
            engine.setProperty("voice", self.voice_id)
        return engine

    def _speak_loop(self):
        # pyttsx3 engines are not thread-safe to share across calls in some
        # backends, so we create one engine instance and reuse it in this
        # single dedicated thread only.
        engine = self._init_engine()
        while not self._stop_event.is_set():
            try:
                phrase = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if phrase is None:
                continue
            try:
                engine.say(phrase)
                engine.runAndWait()
            except Exception as e:
                logger.error(f"TTS error: {e}")

    def speak(self, phrase: str):
        """Queue a phrase to be spoken (non-blocking)."""
        self._queue.put(phrase)
        logger.debug(f"Queued speech: '{phrase}'")

    def clear_queue(self):
        """Drop any pending un-spoken phrases (useful for urgent interrupts)."""
        with self._queue.mutex:
            self._queue.queue.clear()

    def stop(self):
        self._stop_event.set()
        self._thread.join(timeout=2.0)

    @staticmethod
    def list_available_voices():
        """Utility to print available system voices — helpful for picking voice_id."""
        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        for v in voices:
            print(f"id={v.id}  name={v.name}  langs={v.languages}")
