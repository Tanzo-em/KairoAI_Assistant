import os
import struct
import threading
import time

import pvporcupine
import pyaudio
from loguru import logger

from tools.wake_state import trigger_wake
from tools.ui_state import set_ui_status


class PorcupineWakeListener:
    def __init__(self):
        self.access_key = os.getenv("PICOVOICE_ACCESS_KEY")
        self.keyword_path = os.getenv("PORCUPINE_KEYWORD_PATH")

        self._thread = None
        self._stop = threading.Event()

        self.porcupine = None
        self.pa = None
        self.stream = None

    def start(self):
        if not self.access_key:
            logger.warning("PICOVOICE_ACCESS_KEY missing. Porcupine wake disabled.")
            return

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.debug("Porcupine wake listener started")

    def stop(self):
        self._stop.set()

    def _run(self):
        try:
            if self.keyword_path and os.path.exists(self.keyword_path):
                logger.debug(f"Using custom Porcupine keyword: {self.keyword_path}")
                self.porcupine = pvporcupine.create(
                    access_key=self.access_key,
                    keyword_paths=[self.keyword_path],
                    sensitivities=[0.65],
                )
            else:
                logger.warning("Custom Echo .ppn not found. Using built-in keyword: computer")
                self.porcupine = pvporcupine.create(
                    access_key=self.access_key,
                    keywords=["computer"],
                    sensitivities=[0.65],
                )

            self.pa = pyaudio.PyAudio()

            self.stream = self.pa.open(
                rate=self.porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self.porcupine.frame_length,
            )

            logger.debug(
                f"Porcupine ready. sample_rate={self.porcupine.sample_rate}, "
                f"frame_length={self.porcupine.frame_length}"
            )

            while not self._stop.is_set():
                pcm = self.stream.read(
                    self.porcupine.frame_length,
                    exception_on_overflow=False,
                )

                pcm = struct.unpack_from(
                    "h" * self.porcupine.frame_length,
                    pcm,
                )

                keyword_index = self.porcupine.process(pcm)

                if keyword_index >= 0:
                    logger.debug("PORCUPINE WAKE DETECTED")
                    trigger_wake()

                    try:
                        import asyncio
                        loop = asyncio.new_event_loop()
                        loop.run_until_complete(
                            set_ui_status("listening", "Echo is listening")
                        )
                        loop.close()
                    except Exception as e:
                        logger.debug(f"UI wake status update skipped: {e}")

                    time.sleep(1.0)

        except Exception as e:
            logger.exception(f"Porcupine wake listener error: {e}")

        finally:
            try:
                if self.stream:
                    self.stream.stop_stream()
                    self.stream.close()
                if self.pa:
                    self.pa.terminate()
                if self.porcupine:
                    self.porcupine.delete()
            except Exception:
                pass