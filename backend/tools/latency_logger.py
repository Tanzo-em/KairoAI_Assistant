import time
import csv
import os
from loguru import logger
from pipecat.frames.frames import (
    Frame,
    InputAudioRawFrame,
    TranscriptionFrame,
    LLMTextFrame,
    LLMFullResponseStartFrame,
    LLMFullResponseEndFrame,
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
                writer.writerow([
                    'timestamp',
                    'stage',
                    'type',
                    'value',
                    'category',
                    'details',
                ])

    def _log_latency(
        self,
        latency_type: str,
        value: str | float | None = None,
        category: str | None = None,
        details: str | None = None,
    ):
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        value_str = '' if value is None else (f'{value:.3f}' if isinstance(value, float) else str(value))
        with open(self.log_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp,
                self.stage_name,
                latency_type,
                value_str,
                category or '',
                details or '',
            ])


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
                self._log_latency(
                    "stt_latency",
                    stt_latency,
                    category="latency",
                )
            frame.metadata["latency_transcription_received"] = now

        elif isinstance(frame, TTSTextFrame):
            if "latency_transcription_received" in frame.metadata:
                llm_latency = now - frame.metadata["latency_transcription_received"]
                self._log_latency(
                    "llm_latency",
                    llm_latency,
                    category="latency",
                )
            frame.metadata["latency_tts_requested"] = now

        elif isinstance(frame, LLMFullResponseStartFrame):
            self._log_latency(
                "llm_response_start",
                category="llm",
                details="response_start",
            )

        elif isinstance(frame, LLMTextFrame):
            truncated = frame.text.replace("\n", " ")[:512]
            self._log_latency(
                "llm_text_delta",
                category="llm",
                details=truncated,
            )

        elif isinstance(frame, LLMFullResponseEndFrame):
            self._log_latency(
                "llm_response_end",
                category="llm",
                details="response_end",
            )

        elif isinstance(frame, TTSStartedFrame):
            if "latency_tts_requested" in frame.metadata:
                tts_latency = now - frame.metadata["latency_tts_requested"]
                self._log_latency(
                    "tts_start_latency",
                    tts_latency,
                    category="latency",
                )
            if self.audio_received_time:
                e2e_latency = now - self.audio_received_time
                self._log_latency(
                    "e2e_latency",
                    e2e_latency,
                    category="latency",
                )

        await self.push_frame(frame, direction)
