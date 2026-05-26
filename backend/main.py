import os
import asyncio
import re
from contextlib import suppress
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
from pipecat.processors.audio.vad_processor import VADProcessor
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
from pipecat.frames.frames import (
    Frame,
    LLMTextFrame,
    TranscriptionFrame,
    TTSTextFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams
from tools.media_control import MediaCommandProcessor
from tools.ui_state import start_ui_server, set_ui_status
from tools.porcupine_wake import PorcupineWakeListener
from tools.audio_guard import is_bot_speaking, remember_bot_tts
from tools.reminder_manager import ReminderManager
from tools.reminder_processor import ReminderProcessor
from tools.reminder_alert import speak_reminder_alert
from tools.current_info_processor import CurrentInfoProcessor
from tools.wake_state import register_wake_callback
from datetime import datetime
from zoneinfo import ZoneInfo
load_dotenv()

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
logger.add(
    os.path.join(LOG_DIR, "assistant.log"),
    rotation="5 MB",
    retention=5,
    level="DEBUG",
    enqueue=True,
    backtrace=True,
    diagnose=True,
)

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
    def __init__(self):
        super().__init__()
        self.buffer = ""

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TTSTextFrame) and frame.text.strip():
            remember_bot_tts(frame.text)
        elif isinstance(frame, LLMTextFrame):
            self.buffer += frame.text

            if any(punctuation in self.buffer for punctuation in [".", "?", "!"]):
                sentence = self.buffer.strip()
                self.buffer = ""
                remember_bot_tts(sentence)

        await self.push_frame(frame, direction)


class BotSpeechInterruptionGuard(FrameProcessor):
    def __init__(self):
        super().__init__()
        self.suppressing_user_speech = False

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, (UserStartedSpeakingFrame, VADUserStartedSpeakingFrame)):
            if is_bot_speaking():
                self.suppressing_user_speech = True
                logger.debug("SUPPRESSED USER STARTED SPEAKING WHILE BOT SPEAKING")
                return

        if isinstance(frame, (UserStoppedSpeakingFrame, VADUserStoppedSpeakingFrame)):
            if self.suppressing_user_speech:
                self.suppressing_user_speech = False
                logger.debug("SUPPRESSED USER STOPPED SPEAKING WHILE BOT SPEAKING")
                return

        await self.push_frame(frame, direction)


class MusicLLMResponseBlocker(FrameProcessor):
    BLOCKED_PHRASES = (
        "i can't play music directly",
        "i cant play music directly",
        "i cannot play music directly",
        "can't play music directly",
        "cant play music directly",
        "cannot play music directly",
        "preferred music platform",
    )

    def __init__(self):
        super().__init__()
        self.buffer = ""

    def should_block(self, text: str) -> bool:
        cleaned = text.lower().replace("’", "'")
        return any(phrase in cleaned for phrase in self.BLOCKED_PHRASES)

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, LLMTextFrame):
            self.buffer += frame.text

            if not any(punctuation in self.buffer for punctuation in [".", "?", "!"]):
                return

            sentence = self.buffer.strip()
            self.buffer = ""

            if self.should_block(sentence):
                logger.warning(f"SUPPRESSED LLM MUSIC FALLBACK RESPONSE: {sentence}")
                return

            frame.text = sentence
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, TTSTextFrame) and self.should_block(frame.text):
            logger.warning(f"SUPPRESSED TTS MUSIC FALLBACK RESPONSE: {frame.text}")
            return

        await self.push_frame(frame, direction)


class MusicCommandLLMInputBlocker(FrameProcessor):
    PLAY_WORDS = (
        "play",
        "put on",
        "listen to",
        "stream",
        "start playing",
        "find and play",
        "search and play",
    )
    CONTROL_PHRASES = {
        "play",
        "pause",
        "resume",
        "continue",
        "continue playing",
        "keep playing",
        "unpause",
        "next",
        "next song",
        "skip",
        "skip song",
        "previous",
        "prev",
        "previous song",
        "prev song",
        "stop",
        "stop music",
        "stop song",
        "stop playing",
        "volume up",
        "volume down",
        "turn it up",
        "turn it down",
        "mute",
        "unmute",
    }

    def clean_text(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def extract_user_text(self, text: str) -> str:
        match = re.search(r"user said:\s*(.*)\s*$", text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1)

        return text

    def is_music_or_playback_command(self, text: str) -> bool:
        cleaned = self.clean_text(self.extract_user_text(text))

        if cleaned in self.CONTROL_PHRASES:
            return True

        if any(re.search(rf"\b{re.escape(word)}\b", cleaned) for word in self.PLAY_WORDS):
            return True

        return False

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame) and self.is_music_or_playback_command(frame.text):
            logger.warning(f"BLOCKED MUSIC COMMAND BEFORE LLM: {self.extract_user_text(frame.text)}")
            return

        await self.push_frame(frame, direction)


async def reminder_loop(task: PipelineTask, reminder_manager: ReminderManager):
    while True:
        try:
            due_items = reminder_manager.due_items()

            for item in due_items:
                if item["kind"] == "alarm":
                    text = "Alarm ringing. Alarm ringing."
                else:
                    text = f"Reminder: {item['message']}"

                logger.info(f"REMINDER DUE: {text}")

                try:
                    await speak_reminder_alert(text, kind=item["kind"])
                    reminder_manager.mark_done(item["id"])
                    logger.info(f"REMINDER SPOKEN: {item['id']}")
                except Exception as e:
                    reminder_manager.mark_pending(item["id"])
                    logger.error(f"REMINDER SPEAK FAILED: {e}")
        except Exception as e:
            logger.exception(f"REMINDER LOOP ERROR: {e}")

        await asyncio.sleep(1)

async def main():
    wake_processor = WakeWordProcessor()
    media_processor = MediaCommandProcessor()
    register_wake_callback(lambda: media_processor.player.duck(duration_sec=10.0))
    reminder_manager = ReminderManager()
    reminder_processor = ReminderProcessor(reminder_manager)
    current_info_processor = CurrentInfoProcessor()
    vad_processor = VADProcessor(vad_analyzer=SileroVADAnalyzer())
    bot_speech_interruption_guard = BotSpeechInterruptionGuard()
    time_context_processor = TimeContextProcessor()
    music_llm_input_blocker = MusicCommandLLMInputBlocker()
    music_llm_response_blocker = MusicLLMResponseBlocker()
    bot_tts_memory = BotTTSMemoryProcessor()

    logger.debug("Starting echo Assistant")
    porcupine_listener = PorcupineWakeListener()
    porcupine_listener.start()

    ui_server = await start_ui_server()
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
                                    Music playback is handled by Echo's local media controls before the LLM.
                                    If a music request still reaches you, do not say you cannot play music directly.
                                    Ask for the song name or artist in one short sentence.
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
        input_device_index=1,  # Microphone device
    )
)

    pipeline = Pipeline([
        transport.input(),
        vad_processor,
        bot_speech_interruption_guard,
        stt,
        LatencyLogger(stage_name="post-stt"),
        wake_processor,
        media_processor,
        reminder_processor,
        current_info_processor,
        time_context_processor,
        music_llm_input_blocker,
        user_agg,
        llm,
        music_llm_response_blocker,
        LatencyLogger(stage_name="post-llm"),
        bot_tts_memory,
        tts,
        LatencyLogger(stage_name="post-tts"),
        assistant_agg,
    ])

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=False,
        ),
    )

    reminder_task = asyncio.create_task(reminder_loop(task, reminder_manager))
    runner = PipelineRunner()
    try:
        await runner.run(task)
    finally:
        logger.debug("Stopping Echo Assistant cleanup")
        media_processor.player.stop()
        porcupine_listener.stop()
        reminder_task.cancel()
        with suppress(asyncio.CancelledError):
            await reminder_task
        ui_server.close()
        await ui_server.wait_closed()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopping Voxelta Assistant safely...")
