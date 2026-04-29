import os
import asyncio
from dotenv import load_dotenv
from loguru import logger
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
)
from pipecat.frames.frames import Frame, TranscriptionFrame, TTSTextFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams
from tools.media_control import MediaCommandProcessor
load_dotenv()



async def main():
    wake_processor = WakeWordProcessor()
    media_processor = MediaCommandProcessor()
    logger.info("Starting kairo Assistant")

    # STT
    stt = DeepgramSTTService(api_key=os.getenv("DEEPGRAM_API_KEY"))

    # TTS
    tts = OpenAITTSService(
          api_key=os.getenv("OPENAI_API_KEY"),
          model="gpt-4o-mini-tts",
          voice="echo",    
    )

    # LLM
    llm = OpenAIResponsesLLMService(
        api_key=os.getenv("OPENAI_API_KEY"),
        settings=OpenAIResponsesLLMService.Settings(
            model="gpt-4.1-mini",
            system_instruction="""YYou are Echo, the user's personal voice assistant.
            Your wake name is Echo.
            When the user asks your name or wake word, say: My wake word is Echo.
            Reply shortly and naturally.""",
        ),
    )

    # Context
    context = LLMContext()
    user_agg, assistant_agg = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(),
        ),
    )

    # Local mic + speaker
    transport = LocalAudioTransport(
    params=LocalAudioTransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        audio_out_sample_rate=24000,
        audio_in_sample_rate=16000,
    )
)

    pipeline = Pipeline([
        transport.input(),
        stt,
        wake_processor,
        media_processor,
        user_agg,
        llm,
        tts,
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