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
from pipecat.services.openai.tts import OpenAITTSService
from pipecat.services.openai.responses.llm import OpenAIResponsesLLMService

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
load_dotenv()



async def main():
    wake_processor = WakeWordProcessor()
    media_processor = MediaCommandProcessor()
    logger.debug("Starting kairo Assistant")
    porcupine_listener = PorcupineWakeListener()
    porcupine_listener.start()

    await start_ui_server()
    await set_ui_status("sleeping", "Say Echo to wake me")

    # STT
    deepgram_model = os.getenv("DEEPGRAM_STT_MODEL", "nova-3-general")
    stt = DeepgramSTTService(
        api_key=os.getenv("DEEPGRAM_API_KEY"),
        settings=DeepgramSTTService.Settings(
            model=deepgram_model,
            language="en",
            interim_results=True,
            utterance_end_ms=400,
            punctuate=True,
            profanity_filter=False,
        ),
    )

    # TTS
    tts = OpenAITTSService(
        api_key=os.getenv("OPENAI_API_KEY"),
        settings=OpenAITTSService.Settings(
            model=os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
            voice="echo",
        ),
    )

    # LLM
    llm = OpenAIResponsesLLMService(
        api_key=os.getenv("OPENAI_API_KEY"),
        settings=OpenAIResponsesLLMService.Settings(
            model=os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini"),
            temperature=0.7,
            top_p=0.9,
            max_completion_tokens=512,
            system_instruction="""You are Echo, the user's personal voice assistant.
            Your wake name is Echo.
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
        audio_in_device=6,  # PulseAudio device
    )
)

    pipeline = Pipeline([
        transport.input(),
        stt,
        LatencyLogger(stage_name="post-stt"),
        wake_processor,
        media_processor,
        user_agg,
        llm,
        LatencyLogger(stage_name="post-llm"),
        tts,
        LatencyLogger(stage_name="post-tts"),
        transport.output(),
        assistant_agg,
    ])

    task = PipelineTask(
        pipeline,
        params=PipelineParams(),
    )

    runner = PipelineRunner()
    await runner.run(task)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopping Voxelta Assistant safely...")