import time
import re
from loguru import logger
from tools.ui_state import set_ui_status
from tools.wake_state import consume_if_awake, sleep_now

from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection


class WakeWordProcessor(FrameProcessor):
    def __init__(self):
        super().__init__()

        self.awake = False
        self.last_command_time = 0
        self.sleep_timeout_sec = 30

    def clean_text(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def is_timeout(self):
        return self.awake and (time.time() - self.last_command_time > self.sleep_timeout_sec)

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame):
            original_text = frame.text.strip()
            cleaned_text = self.clean_text(original_text)

            logger.info(f"HEARD RAW: {original_text}")
            logger.info(f"HEARD CLEAN: {cleaned_text}")

            if self.is_timeout():
                self.awake = False
                sleep_now()
                logger.info("ECHO BACK TO SLEEP AFTER 30 SECONDS")
                await set_ui_status("sleeping", "Echo is sleeping")
                return

            if consume_if_awake():
                self.awake = True

            # Fallback wake detection from Deepgram if Porcupine did not detect
            fallback_wake_words = [
                "echo",
                "hey echo",
                "hello echo",
                "ok echo",
                "okay echo",
                "he echo",
                "the echo",
            ]

            fallback_wake = any(w in cleaned_text for w in fallback_wake_words)

            if not self.awake:
                if fallback_wake:
                    logger.info(f"STT FALLBACK WAKE DETECTED: {cleaned_text}")
                    self.awake = True
                    self.last_command_time = time.time()
                    await set_ui_status("listening", "Echo is listening")

                    # If user only said wake word, wait for next command
                    command_text = cleaned_text
                    for w in fallback_wake_words:
                        command_text = command_text.replace(w, "", 1).strip()

                    if not command_text:
                        logger.info("ECHO IS AWAKE. WAITING FOR COMMAND.")
                        return

                    frame.text = command_text
                    logger.info(f"COMMAND WITH FALLBACK WAKE: {command_text}")
                    await self.push_frame(frame, direction)
                    return

                logger.debug(f"WAITING FOR PORCUPINE WAKE. IGNORED: {original_text}")
                return

            if not cleaned_text:
                return

            # Avoid sending the wake word itself as the command.
            if cleaned_text in ["echo", "hey echo", "hello echo", "ok echo", "okay echo"]:
                logger.debug("IGNORED WAKE WORD TEXT FROM STT")
                return

            self.last_command_time = time.time()
            logger.info(f"COMMAND RECEIVED AFTER PORCUPINE WAKE: {original_text}")

            await self.push_frame(frame, direction)
            return

        await self.push_frame(frame, direction)