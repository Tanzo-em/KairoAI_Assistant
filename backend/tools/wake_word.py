import time
import re
from loguru import logger
from tools.ui_state import set_ui_status
from tools.wake_state import consume_if_awake, sleep_now
from tools.audio_guard import is_probably_bot_echo
from pipecat.frames.frames import Frame, TranscriptionFrame, TTSTextFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection


class WakeWordProcessor(FrameProcessor):
    def __init__(self):
        super().__init__()

        self.awake = False
        self.last_command_time = 0
        self.sleep_timeout_sec = 180

    def clean_text(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def is_timeout(self):
        return self.awake and (time.time() - self.last_command_time > self.sleep_timeout_sec)

    def parse_wake_and_command(self, text: str):
        fallback_wake_words = [
            "echo",
            "hey echo",
            "hello echo",
            "ok echo",
            "okay echo",
            "he echo",
            "the echo",
        ]

        for wake in fallback_wake_words:
            if text == wake:
                return wake, ""
            if text.startswith(wake + " "):
                return wake, text[len(wake) :].strip()

        return None, text

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame):
            original_text = frame.text.strip()
            cleaned_text = self.clean_text(original_text)

            logger.debug(f"HEARD RAW: {original_text}")
            logger.debug(f"HEARD CLEAN: {cleaned_text}")


            if is_probably_bot_echo(cleaned_text):
                logger.debug(f"IGNORED BOT SPEAKER ECHO: {original_text}")
                return

            wake, command_text = self.parse_wake_and_command(cleaned_text)

            if self.is_timeout():
                self.awake = False
                logger.debug("ECHO BACK TO SLEEP AFTER TIMEOUT")
                await set_ui_status("sleeping", "Echo is sleeping")

                if not wake:
                    sleep_now()
                    return

                logger.debug("TIMEOUT EXPIRED BUT WAKE WORD DETECTED: resuming on STT wake")

            if consume_if_awake():
                self.awake = True
                self.last_command_time = time.time()

                if wake:
                    if not command_text:
                        logger.debug("ECHO IS AWAKE. SAYING GREETING AND WAITING FOR COMMAND.")
                        await self.push_frame(
                            TTSTextFrame(
                                text="Hello! How can I help you today?",
                                aggregated_by="wake_greeting",
                            ),
                            direction,
                        )
                        return

                    frame.text = command_text
                    logger.debug(f"COMMAND AFTER PORCUPINE WAKE WITH WAKE WORD: {command_text}")
                    await self.push_frame(frame, direction)
                    return

                logger.debug(f"COMMAND RECEIVED AFTER PORCUPINE WAKE: {original_text}")
                await self.push_frame(frame, direction)
                return

            if not self.awake:
                if wake:
                    logger.debug(f"STT FALLBACK WAKE DETECTED: {cleaned_text}")
                    self.awake = True
                    self.last_command_time = time.time()
                    await set_ui_status("listening", "Echo is listening")

                    if not command_text:
                        logger.debug("ECHO IS AWAKE. SAYING GREETING AND WAITING FOR COMMAND.")
                        await self.push_frame(
                            TTSTextFrame(
                                text="Hello! How can I help today?",
                                aggregated_by="wake_greeting",
                            ),
                            direction,
                        )
                        return

                    frame.text = command_text
                    logger.debug(f"COMMAND WITH FALLBACK WAKE: {command_text}")
                    await self.push_frame(frame, direction)
                    return

                logger.debug(f"WAITING FOR PORCUPINE WAKE. IGNORED: {original_text}")
                return

            if not cleaned_text:
                return

            if wake and not command_text:
                logger.debug("IGNORED WAKE WORD TEXT FROM STT")
                return

            self.last_command_time = time.time()
            logger.debug(f"COMMAND RECEIVED AFTER PORCUPINE WAKE: {original_text}")

            await self.push_frame(frame, direction)
            return

        await self.push_frame(frame, direction)