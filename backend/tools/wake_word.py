import time
import re
from loguru import logger

from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection


class WakeWordProcessor(FrameProcessor):
    def __init__(self):
        super().__init__()

        self.awake = False
        self.last_command_time = 0
        self.sleep_timeout_sec = 30

        # Add all possible words Deepgram may hear
        self.wake_words = [
            "echo",
            "hey echo",
            "hello echo",
            "ok echo",
            "he echo"

        ]

    def clean_text(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def is_wake_word_detected(self, text: str):
        for wake in self.wake_words:
            if wake in text:
                return wake
        return None

    def remove_wake_word(self, text: str, wake: str):
        return text.replace(wake, "", 1).strip()

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
                logger.info("ECHO BACK TO SLEEP AFTER 30 SECONDS")

            wake = self.is_wake_word_detected(cleaned_text)

            # Sleeping mode
            if not self.awake:
                if not wake:
                    logger.debug(f"SLEEPING. IGNORED: {original_text}")
                    return

                logger.info(f"WAKE WORD DETECTED: {wake}")
                self.awake = True
                self.last_command_time = time.time()

                command_text = self.remove_wake_word(cleaned_text, wake)

                if command_text:
                    logger.info(f"COMMAND WITH WAKE WORD: {command_text}")
                    frame.text = command_text
                    await self.push_frame(frame, direction)
                    return

                logger.info("ECHO IS AWAKE. WAITING FOR COMMAND.")
                return

            # Awake mode
            self.last_command_time = time.time()
            logger.info(f"COMMAND RECEIVED: {original_text}")
            await self.push_frame(frame, direction)
            return

        await self.push_frame(frame, direction)

        