import asyncio
from pathlib import Path

from loguru import logger
from pipecat.frames.frames import Frame, LLMTextFrame, TTSTextFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection

from .sherpa_integration import sherpa_installed, sherpa_models_present, speak_with_sherpa_tts


class SherpaTTSProcessor(FrameProcessor):
    def __init__(self):
        super().__init__()
        self.buffer = ""

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, (LLMTextFrame, TTSTextFrame)):
            self.buffer += frame.text

            if isinstance(frame, TTSTextFrame) and self.buffer.strip():
                sentence = self.buffer.strip()
                self.buffer = ""
                logger.info(f"Sherpa TTS speaking immediately: {sentence}")
                if not (sherpa_installed() and sherpa_models_present()):
                    logger.warning("Sherpa TTS not available")
                else:
                    await asyncio.to_thread(speak_with_sherpa_tts, sentence)
            elif any(p in self.buffer for p in [".", "?", "!"]):
                sentence = self.buffer.strip()
                self.buffer = ""
                logger.info(f"Sherpa TTS speaking: {sentence}")
                if not (sherpa_installed() and sherpa_models_present()):
                    logger.warning("Sherpa TTS not available")
                else:
                    await asyncio.to_thread(speak_with_sherpa_tts, sentence)

        await self.push_frame(frame, direction)
