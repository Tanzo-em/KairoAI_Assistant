import asyncio
import os
import subprocess
import tempfile
from pathlib import Path

from gtts import gTTS
from loguru import logger
from pipecat.frames.frames import (
    Frame,
    InterruptionFrame,
    LLMTextFrame,
    TTSTextFrame,
    UserStartedSpeakingFrame,
    VADUserStartedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from tools.audio_playback import (
    play_wav_interruptible,
    playback_generation,
    stop_current_playback,
    was_playback_stopped_since,
)

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "tmp" / "gtts_audio"


def _convert_mp3_to_wav(mp3_path: Path, wav_path: Path) -> None:
    process = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(mp3_path),
            "-ar",
            "24000",
            "-ac",
            "1",
            str(wav_path),
        ],
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        raise RuntimeError(
            f"ffmpeg conversion failed: {process.stderr.strip()}"
        )


def _play_wav(wav_path: Path, generation: int | None = None) -> None:
    play_wav_interruptible(wav_path, generation=generation)


def _speak_with_gtts(text: str) -> None:
    text = text.strip()
    if not text:
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generation = playback_generation()
    fd, mp3_path = tempfile.mkstemp(suffix=".mp3", dir=OUTPUT_DIR)
    os.close(fd)
    mp3_path = Path(mp3_path)
    wav_path = mp3_path.with_suffix(".wav")

    try:
        tts = gTTS(text, lang="en")
        tts.save(str(mp3_path))
        if was_playback_stopped_since(generation):
            return
        _convert_mp3_to_wav(mp3_path, wav_path)
        if was_playback_stopped_since(generation):
            return
        _play_wav(wav_path, generation=generation)
    finally:
        mp3_path.unlink(missing_ok=True)
        wav_path.unlink(missing_ok=True)


async def speak_with_gtts(text: str) -> None:
    await asyncio.to_thread(_speak_with_gtts, text)


class GTTSProcessor(FrameProcessor):
    def __init__(self):
        super().__init__()
        self.buffer = ""

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(
            frame,
            (InterruptionFrame, VADUserStartedSpeakingFrame, UserStartedSpeakingFrame),
        ):
            self.buffer = ""
            stop_current_playback()
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, (LLMTextFrame, TTSTextFrame)):
            self.buffer += frame.text

            if isinstance(frame, TTSTextFrame) and self.buffer.strip():
                sentence = self.buffer.strip()
                self.buffer = ""
                logger.info(f"gTTS speaking immediately: {sentence}")
                await speak_with_gtts(sentence)
            elif any(p in self.buffer for p in [".", "?", "!"]):
                sentence = self.buffer.strip()
                self.buffer = ""
                logger.info(f"gTTS speaking: {sentence}")
                await speak_with_gtts(sentence)

        await self.push_frame(frame, direction)
