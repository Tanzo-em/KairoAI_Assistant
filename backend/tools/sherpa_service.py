import asyncio
import tempfile
from pathlib import Path

from loguru import logger

from pipecat.frames.frames import TranscriptionFrame
from pipecat.services.stt_service import SegmentedSTTService
from pipecat.utils.time import time_now_iso8601

from .sherpa_integration import transcribe_file_with_sherpa, sherpa_installed, sherpa_models_present


class SherpaSTTService(SegmentedSTTService):
    """A lightweight Segmented STT adapter that uses sherpa_onnx offline models.

    It writes the incoming WAV bytes to a temp file and calls the helper
    `transcribe_file_with_sherpa` to produce text.
    """

    def __init__(self, *, sample_rate: int | None = None, **kwargs):
        super().__init__(sample_rate=sample_rate, **kwargs)

    async def run_stt(self, audio: bytes):
        if not sherpa_installed() or not sherpa_models_present():
            await self.push_error("Sherpa not installed or models missing")
            return

        # Save bytes to a temp wav file and run transcription in a thread
        fd, tmp = tempfile.mkstemp(suffix=".wav")
        Path(tmp).write_bytes(audio)
        try:
            text = await asyncio.to_thread(transcribe_file_with_sherpa, tmp)
        except Exception as e:
            logger.error(f"Sherpa transcription failed: {e}")
            await self.push_error(f"Sherpa transcription failed: {e}")
            Path(tmp).unlink(missing_ok=True)
            return
        Path(tmp).unlink(missing_ok=True)

        frame = TranscriptionFrame(text, self._user_id, time_now_iso8601(), None, result=None)
        yield frame
