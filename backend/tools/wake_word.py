import time
import re
from loguru import logger
from tools.ui_state import set_ui_status
from tools.wake_state import consume_if_awake, sleep_now
from tools.audio_guard import is_bot_speaking, is_probably_bot_riko
from tools.audio_playback import stop_current_playback
from pipecat.frames.frames import Frame, TranscriptionFrame, TTSTextFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection


WAKE_WORD_ALIASES = (
    "riko",
    "rico",
    "ricko",
    "rikko",
    "reeko",
    "reico",
    "reiko",
    "ryko",
    "riku",
    "biko",
    "viko",
)
WAKE_PREFIXES = ("", "hey ", "hello ", "ok ", "okay ", "he ", "the ")


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
            f"{prefix}{alias}".strip()
            for alias in WAKE_WORD_ALIASES
            for prefix in WAKE_PREFIXES
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
            frame.metadata["explicit_wake_word"] = False
            frame.metadata["wake_activated"] = False

            logger.debug(f"HEARD RAW: {original_text}")
            logger.debug(f"HEARD CLEAN: {cleaned_text}")

            wake, command_text = self.parse_wake_and_command(cleaned_text)

            if is_probably_bot_riko(cleaned_text):
                logger.debug(f"IGNORED BOT SPEAKER RIKO: {original_text}")
                return

            if is_bot_speaking():
                if not wake:
                    logger.debug(f"IGNORED AUDIO WHILE BOT SPEAKING: {original_text}")
                    return

                logger.debug(f"USER INTERRUPTED BOT SPEECH WITH WAKE WORD: {original_text}")
                stop_current_playback()
                await self.broadcast_interruption()

            if self.is_timeout():
                self.awake = False
                logger.debug("RIKO BACK TO SLEEP AFTER TIMEOUT")
                await set_ui_status("sleeping", "Riko is sleeping")

                if not wake:
                    sleep_now()
                    return

                logger.debug("TIMEOUT EXPIRED BUT WAKE WORD DETECTED: resuming on STT wake")

            if consume_if_awake():
                self.awake = True
                self.last_command_time = time.time()
                frame.metadata["wake_activated"] = True

                if wake:
                    frame.metadata["explicit_wake_word"] = True
                    if not command_text:
                        logger.debug("RIKO IS AWAKE. SAYING GREETING AND WAITING FOR COMMAND.")
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
                    frame.metadata["explicit_wake_word"] = True
                    frame.metadata["wake_activated"] = True
                    logger.debug(f"STT FALLBACK WAKE DETECTED: {cleaned_text}")
                    self.awake = True
                    self.last_command_time = time.time()
                    await set_ui_status("listening", "Riko is listening")

                    if not command_text:
                        logger.debug("RIKO IS AWAKE. SAYING GREETING AND WAITING FOR COMMAND.")
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

            if wake:
                frame.metadata["explicit_wake_word"] = True
                frame.metadata["wake_activated"] = True
                frame.text = command_text

            self.last_command_time = time.time()
            logger.debug(f"COMMAND RECEIVED AFTER PORCUPINE WAKE: {original_text}")

            await self.push_frame(frame, direction)
            return

        await self.push_frame(frame, direction)
