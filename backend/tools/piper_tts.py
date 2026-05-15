import asyncio
import subprocess
import tempfile
from pathlib import Path
from loguru import logger

from pipecat.frames.frames import Frame, LLMTextFrame, TTSTextFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection

BASE_DIR = Path(__file__).resolve().parent.parent
PIPER_MODEL = BASE_DIR / "models" / "piper" / "en_US-amy-medium.onnx"


async def speak_with_piper(text: str) -> None:
    text = text.strip()
    if not text:
        return

    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav_file:
            wav_path = wav_file.name

        # Use piper CLI to synthesize
        process = await asyncio.create_subprocess_exec(
            'bash', '-c',
            f'echo "{text}" | piper --model {PIPER_MODEL} --output_file {wav_path}',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            # Play the audio
            play_process = await asyncio.create_subprocess_exec(
                'aplay', wav_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await play_process.communicate()
            
            # Clean up
            Path(wav_path).unlink()
        else:
            logger.error(f"Piper synthesis failed: {stderr.decode()}")

    except Exception as e:
        logger.error(f"Piper TTS error: {e}")


class PiperTTSProcessor(FrameProcessor):
    def __init__(self):
        super().__init__()
        self.buffer = ""

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, (LLMTextFrame, TTSTextFrame)):
            text = frame.text
            self.buffer += text

            # For TTSTextFrame (like wake greetings), speak immediately
            if isinstance(frame, TTSTextFrame) and self.buffer.strip():
                sentence = self.buffer.strip()
                self.buffer = ""
                logger.info(f"PIPER SPEAKING IMMEDIATELY: {sentence}")
                await speak_with_piper(sentence)
            elif any(p in self.buffer for p in [".", "?", "!"]):
                sentence = self.buffer.strip()
                self.buffer = ""
                logger.info(f"PIPER SPEAKING: {sentence}")
                await speak_with_piper(sentence)

            await self.push_frame(frame, direction)
            return

        await self.push_frame(frame, direction)