import asyncio
import os
import subprocess
import tempfile
import time
from pathlib import Path

try:
    import edge_tts
except Exception:
    edge_tts = None

from loguru import logger
from pipecat.frames.frames import Frame, LLMTextFrame, TTSTextFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "tmp" / "edge_tts_audio"
DEFAULT_VOICE = "en-US-AriaNeural"


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
        raise RuntimeError(f"ffmpeg conversion failed: {process.stderr.strip()}")


async def _stream_to_file(text: str, voice: str, out_path: str) -> str:
    communicator = edge_tts.Communicate(text, voice)
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("wb") as f:
        async for chunk in communicator.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
    return str(out_file)


def _play_wav(wav_path: Path) -> None:
    process = subprocess.run(
        ["aplay", str(wav_path)],
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        raise RuntimeError(f"aplay failed: {process.stderr.strip()}")


def _speak_with_edge_tts(text: str, voice: str = DEFAULT_VOICE) -> str:
    if edge_tts is None:
        raise RuntimeError("edge-tts package is not installed")

    text = text.strip()
    if not text:
        return ""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fd, mp3_path = tempfile.mkstemp(suffix=".mp3", dir=OUTPUT_DIR)
    os.close(fd)
    mp3_path = Path(mp3_path)
    wav_path = mp3_path.with_suffix(".wav")

    try:
        asyncio.run(_stream_to_file(text, voice, str(mp3_path)))
        _convert_mp3_to_wav(mp3_path, wav_path)
        _play_wav(wav_path)
    finally:
        mp3_path.unlink(missing_ok=True)
        wav_path.unlink(missing_ok=True)

    return str(wav_path)


async def speak_with_edge_tts(text: str, voice: str = DEFAULT_VOICE) -> None:
    await asyncio.to_thread(_speak_with_edge_tts, text, voice)


class EdgeTTSProcessor(FrameProcessor):
    def __init__(self, voice: str = DEFAULT_VOICE):
        super().__init__()
        self.voice = voice
        self.buffer = ""

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, (LLMTextFrame, TTSTextFrame)):
            self.buffer += frame.text

            if isinstance(frame, TTSTextFrame) and self.buffer.strip():
                sentence = self.buffer.strip()
                self.buffer = ""
                logger.info(f"EdgeTTS speaking immediately: {sentence}")
                await speak_with_edge_tts(sentence, voice=self.voice)
            elif any(p in self.buffer for p in [".", "?", "!"]):
                sentence = self.buffer.strip()
                self.buffer = ""
                logger.info(f"EdgeTTS speaking: {sentence}")
                await speak_with_edge_tts(sentence, voice=self.voice)

        await self.push_frame(frame, direction)


if __name__ == "__main__":
    # quick manual test
    text = "Hello. This is a test of a more natural, neural voice."
    print("Synthesizing...")
    p = _speak_with_edge_tts(text)
    print("WAV saved to:", p)
