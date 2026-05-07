import time
import csv
import os
from loguru import logger
from pipecat.frames.frames import (
    Frame,
    InputAudioRawFrame,
    TranscriptionFrame,
    TTSTextFrame,
    TTSStartedFrame,
    OutputAudioRawFrame,
    TTSAudioRawFrame,
)
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection


class LatencyLogger(FrameProcessor):
    def __init__(self, stage_name: str = "latency", log_file: str = "latency_log.csv"):
        super().__init__()
        self.stage_name = stage_name
        self.log_file = log_file
        self.audio_received_time = None
        self._ensure_csv_header()

    def _ensure_csv_header(self):
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'stage', 'type', 'value'])

    def _log_latency(self, latency_type: str, value: float):
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        with open(self.log_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, self.stage_name, latency_type, f'{value:.3f}'])


    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        now = time.perf_counter()

        if isinstance(frame, InputAudioRawFrame):
            self.audio_received_time = now
            frame.metadata["latency_audio_received"] = now
            # Removed logging to prevent infinite loop from continuous audio frames

        elif isinstance(frame, TranscriptionFrame):
            if "latency_audio_received" in frame.metadata:
                stt_latency = now - frame.metadata["latency_audio_received"]
                self._log_latency("stt_latency", stt_latency)
            frame.metadata["latency_transcription_received"] = now

        elif isinstance(frame, TTSTextFrame):
            if "latency_transcription_received" in frame.metadata:
                llm_latency = now - frame.metadata["latency_transcription_received"]
                self._log_latency("llm_latency", llm_latency)
            frame.metadata["latency_tts_requested"] = now

        elif isinstance(frame, TTSStartedFrame):
            if "latency_tts_requested" in frame.metadata:
                tts_latency = now - frame.metadata["latency_tts_requested"]
                self._log_latency("tts_start_latency", tts_latency)
            if self.audio_received_time:
                e2e_latency = now - self.audio_received_time
                self._log_latency("e2e_latency", e2e_latency)

        elif isinstance(frame, (TTSAudioRawFrame, OutputAudioRawFrame)):
            logger.debug(
                f"[{self.stage_name}] audio output frame, size={len(frame.audio)} sample_rate={frame.sample_rate}"
            )

        await self.push_frame(frame, direction)
