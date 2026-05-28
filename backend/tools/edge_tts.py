import asyncio
import os
import subprocess
import tempfile
from pathlib import Path

try:
    import edge_tts
except Exception:
    edge_tts = None

from loguru import logger
from pipecat.frames.frames import (
    Frame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
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


def _play_wav(wav_path: Path, generation: int | None = None) -> None:
    play_wav_interruptible(wav_path, generation=generation)


def _speak_with_edge_tts(text: str, voice: str = DEFAULT_VOICE) -> str:
    if edge_tts is None:
        raise RuntimeError("edge-tts package is not installed")

    text = text.strip()
    if not text:
        return ""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generation = playback_generation()
    fd, mp3_path = tempfile.mkstemp(suffix=".mp3", dir=OUTPUT_DIR)
    os.close(fd)
    mp3_path = Path(mp3_path)
    wav_path = mp3_path.with_suffix(".wav")

    try:
        asyncio.run(_stream_to_file(text, voice, str(mp3_path)))
        if was_playback_stopped_since(generation):
            return ""
        _convert_mp3_to_wav(mp3_path, wav_path)
        if was_playback_stopped_since(generation):
            return ""
        _play_wav(wav_path, generation=generation)
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
        self.queue = asyncio.Queue()
        self.worker_task = None
        self.min_chunk_chars = 35
        self.max_chunk_chars = 180
        self.soft_break_chars = 120

    async def _ensure_worker(self):
        if self.worker_task is None or self.worker_task.done():
            self.worker_task = asyncio.create_task(self._speaker_worker())

    async def _speaker_worker(self):
        while True:
            sentence = await self.queue.get()
            try:
                if sentence is None:
                    return

                logger.info(f"EdgeTTS queued speaking: {sentence}")
                await speak_with_edge_tts(sentence, voice=self.voice)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"EdgeTTS queued speaking failed: {e}")
            finally:
                self.queue.task_done()

    def _clear_queue(self):
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except asyncio.QueueEmpty:
                break

    async def _enqueue_text(self, text: str):
        text = text.strip()
        if not text:
            return

        await self._ensure_worker()
        await self.queue.put(text)

    def _pop_speakable_chunk(self, *, force: bool = False) -> str | None:
        text = self.buffer.strip()

        if not text:
            self.buffer = ""
            return None

        terminal_positions = [
            text.find(punctuation)
            for punctuation in [".", "?", "!"]
            if text.find(punctuation) >= 0
        ]

        if terminal_positions:
            end = min(terminal_positions) + 1
            chunk = text[:end].strip()
            self.buffer = text[end:].lstrip()
            return chunk

        if force:
            self.buffer = ""
            return text

        if len(text) < self.min_chunk_chars:
            return None

        break_at = -1
        for punctuation in [",", ";", ":"]:
            pos = text.rfind(punctuation, 0, self.max_chunk_chars)
            if pos >= self.min_chunk_chars:
                break_at = max(break_at, pos + 1)

        if break_at < 0 and len(text) >= self.soft_break_chars:
            pos = text.rfind(" ", 0, self.max_chunk_chars)
            if pos >= self.min_chunk_chars:
                break_at = pos

        if break_at < 0:
            return None

        chunk = text[:break_at].strip()
        self.buffer = text[break_at:].lstrip()
        return chunk

    async def _flush_ready_chunks(self, *, force: bool = False):
        while True:
            chunk = self._pop_speakable_chunk(force=force)
            if not chunk:
                return
            await self._enqueue_text(chunk)
            if force:
                force = False

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(
            frame,
            (InterruptionFrame, VADUserStartedSpeakingFrame, UserStartedSpeakingFrame),
        ):
            if isinstance(frame, InterruptionFrame):
                logger.debug("EdgeTTS interruption: clearing queued speech")
                self.buffer = ""
                self._clear_queue()
                stop_current_playback()
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, TTSTextFrame):
            self.buffer += frame.text
            await self._flush_ready_chunks(force=True)

        elif isinstance(frame, LLMTextFrame):
            self.buffer += frame.text
            await self._flush_ready_chunks()

        elif isinstance(frame, LLMFullResponseEndFrame):
            await self._flush_ready_chunks(force=True)

        await self.push_frame(frame, direction)


if __name__ == "__main__":
    # quick manual test
    text = "Hello. This is a test of a more natural, neural voice."
    print("Synthesizing...")
    p = _speak_with_edge_tts(text)
    print("WAV saved to:", p)
