import os
import asyncio
from dotenv import load_dotenv
from loguru import logger
from tools.latency_logger import LatencyLogger
from tools.wake_word import WakeWordProcessor
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.pipeline.runner import PipelineRunner
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.openai.responses.llm import OpenAIResponsesLLMService
from tools.gtts_tts import GTTSProcessor
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
    LLMAssistantAggregatorParams,
)
from pipecat.utils.context.llm_context_summarization import (
    LLMAutoContextSummarizationConfig,
    LLMContextSummaryConfig,
)
from pipecat.frames.frames import Frame, TranscriptionFrame, TTSTextFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams
from tools.media_control import MediaCommandProcessor
from tools.ui_state import start_ui_server, set_ui_status
from tools.porcupine_wake import PorcupineWakeListener
from tools.audio_guard import remember_bot_tts
from datetime import datetime
from zoneinfo import ZoneInfo
load_dotenv()

class TimeContextProcessor(FrameProcessor):
    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame):
            now = datetime.now(ZoneInfo("Asia/Kolkata"))
            current_datetime = now.strftime("%A, %d %B %Y, %I:%M:%S %p")

            original_text = frame.text.strip()

            frame.text = (
                f"[Current date and time: {current_datetime}. "
                f"Timezone: Asia/Kolkata, India.]\n\n"
                f"User said: {original_text}"
            )

        await self.push_frame(frame, direction)

class BotTTSMemoryProcessor(FrameProcessor):
    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TTSTextFrame):
            remember_bot_tts(frame.text)

        await self.push_frame(frame, direction)


async def main():
    wake_processor = WakeWordProcessor()
    media_processor = MediaCommandProcessor()
    time_context_processor = TimeContextProcessor()
    bot_tts_memory = BotTTSMemoryProcessor()
    logger.debug("Starting echo Assistant")
    porcupine_listener = PorcupineWakeListener()
    porcupine_listener.start()

    await start_ui_server()
    await set_ui_status("sleeping", "Say Echo to wake me")

    # STT and TTS selection (Deepgram/gTTS by default; Sherpa if available or requested)
    use_sherpa_env = os.getenv("USE_SHERPA", "0")
    try:
        from tools.sherpa_integration import sherpa_installed, sherpa_models_present
        sherpa_available = sherpa_installed() and sherpa_models_present()
    except Exception:
        sherpa_available = False

    if use_sherpa_env == "1" and sherpa_available:
        from tools.sherpa_service import SherpaSTTService
        from tools.sherpa_tts import SherpaTTSProcessor

        stt = SherpaSTTService()
        tts = SherpaTTSProcessor()
    else:
        # Default pipeline uses Edge TTS for a more natural voice and falls back to gTTS if needed.
        stt = DeepgramSTTService(api_key=os.getenv("DEEPGRAM_API_KEY"))
        use_gtts_env = os.getenv("USE_GTTTS", "0")
        if use_gtts_env == "1":
            tts = GTTSProcessor()
        else:
            try:
                from tools.edge_tts import EdgeTTSProcessor

                tts = EdgeTTSProcessor()
            except Exception as e:
                logger.warning(f"edge-tts unavailable, falling back to gTTS: {e}")
                tts = GTTSProcessor()

    # LLM
    llm = OpenAIResponsesLLMService(
        api_key=os.getenv("OPENAI_API_KEY"),
        settings=OpenAIResponsesLLMService.Settings(
            model=os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini"),
            temperature=0.7,
            top_p=0.9,
            max_completion_tokens=256,
            system_instruction="""You are Echo, the user's personal voice assistant.
                                    Your wake name is Echo.

                                    The current date and time may be provided inside the user's message.
                                    When the user asks today's date, current time, day, month, or year, use the provided current date/time.
                                    Do not guess the date or time.

                                    When the user asks your name or wake word, say: My wake word is Echo.
                                    Reply shortly and naturally.""",
        ),
    )

    # Context
    context = LLMContext()

    assistant_params = LLMAssistantAggregatorParams(
        enable_auto_context_summarization=True,
        auto_context_summarization_config=LLMAutoContextSummarizationConfig(
            max_context_tokens=2500,
            max_unsummarized_messages=8,
            summary_config=LLMContextSummaryConfig(
                target_context_tokens=1200,
                min_messages_after_summary=3,
            ),
        ),
    )

    user_agg, assistant_agg = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(),
        ),
        assistant_params=assistant_params,
    )

    # Local mic + speaker
    transport = LocalAudioTransport(
    params=LocalAudioTransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        audio_out_sample_rate=24000,
        audio_in_sample_rate=16000,
        audio_in_device=1,  # Microphone device
    )
)

    pipeline = Pipeline([
        transport.input(),
        stt,
        LatencyLogger(stage_name="post-stt"),
        wake_processor,
        media_processor,
        time_context_processor,
        user_agg,
        llm,
        LatencyLogger(stage_name="post-llm"),
        tts,
        bot_tts_memory,
        LatencyLogger(stage_name="post-tts"),
        assistant_agg,
    ])

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=False,
        ),
    )

    runner = PipelineRunner()
    await runner.run(task)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopping Voxelta Assistant safely...")