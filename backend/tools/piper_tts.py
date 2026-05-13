import asyncio
import subprocess
import tempfile
from pathlib import Path
from loguru import logger

from pipecat.frames.frames import Frame, LLMTextFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection

BASE_DIR = Path(__file__).resolve().parent.parent
PIPER_MODEL = BASE_DIR / "models" / "piper" / "en_US-amy-medium.onnx"


def speak_with_piper(text: str) -> None:
    text = text.strip()
    if not text:
        return

    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as wav_file:
            wav_path = wav_file.name

            subprocess.run(
                [
                    "uv",
                    "run",
                    "piper",
                    "--model",
                    str(PIPER_MODEL),
                    "--output_file",
                    wav_path,
                ],
                input=text,
                text=True,
                check=True,
            )

            subprocess.run(["aplay", wav_path], check=True)

    except Exception as e:
        logger.error(f"Piper TTS error: {e}")


class PiperTTSProcessor(FrameProcessor):
    def __init__(self):
        super().__init__()
        self.buffer = ""

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, LLMTextFrame):
            text = frame.text
            self.buffer += text

            if any(p in self.buffer for p in [".", "?", "!"]):
                sentence = self.buffer.strip()
                self.buffer = ""

                logger.info(f"PIPER SPEAKING: {sentence}")
                await asyncio.to_thread(speak_with_piper, sentence)

            await self.push_frame(frame, direction)
            return

        await self.push_frame(frame, direction)