import os
import asyncio
from contextlib import suppress
from dotenv import load_dotenv
from loguru import logger
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.pipeline.runner import PipelineRunner
from pipecat.services.openai.realtime import events
from pipecat.services.openai.realtime.llm import OpenAIRealtimeLLMService
from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams
from tools.ui_state import start_ui_server, set_ui_status
from tools.reminder_manager import ReminderManager
from tools.openai_realtime2 import (
    OpenAIRealtime2Service,
    RealtimeLocalTools,
)
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

async def reminder_loop(realtime: OpenAIRealtime2Service, reminder_manager: ReminderManager):
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
                    await realtime.speak_text(text)
                    reminder_manager.mark_done(item["id"])
                    logger.info(f"REMINDER SPOKEN: {item['id']}")
                except Exception as e:
                    reminder_manager.mark_pending(item["id"])
                    logger.error(f"REMINDER SPEAK FAILED: {e}")
        except Exception as e:
            logger.exception(f"REMINDER LOOP ERROR: {e}")

        await asyncio.sleep(1)

async def main():
    reminder_manager = ReminderManager()
    local_tools = RealtimeLocalTools(reminder_manager)

    logger.debug("Starting Riko Assistant")

    ui_server = await start_ui_server()
    await set_ui_status("listening", "Riko is listening")

    system_instruction = """You are Riko, the user's personal voice assistant.
Your wake name is Riko.

The current date and time may be provided inside the user's message.
When the user asks today's date, current time, day, month, or year, use the provided current date/time.
Do not guess the date or time.

Porcupine wake word is disabled in this environment, so respond naturally when the user speaks.
Use get_local_datetime for date or time questions.
Use control_media for music and playback commands.
Use set_reminder for alarm and reminder requests.
Use get_current_info for weather, news, scores, prices, availability, and other current information.
Reply shortly and naturally.
Do not introduce your abilities or list commands unless the user asks what you can do."""

    realtime = OpenAIRealtime2Service(
        local_tools=local_tools,
        api_key=os.getenv("OPENAI_API_KEY"),
        settings=OpenAIRealtimeLLMService.Settings(
            model=os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime-2"),
            system_instruction=system_instruction,
            max_tokens=512,
            session_properties=events.SessionProperties(
                output_modalities=["audio"],
                instructions=system_instruction,
                audio=events.AudioConfiguration(
                    input=events.AudioInput(
                        format=events.PCMAudioFormat(),
                        transcription=events.InputAudioTranscription(
                            model=os.getenv(
                                "OPENAI_REALTIME_TRANSCRIPTION_MODEL",
                                "gpt-4o-transcribe",
                            ),
                            language="en",
                        ),
                        noise_reduction=events.InputAudioNoiseReduction(type="near_field"),
                        turn_detection=events.SemanticTurnDetection(
                            eagerness="auto",
                            create_response=False,
                            interrupt_response=True,
                        ),
                    ),
                    output=events.AudioOutput(
                        format=events.PCMAudioFormat(),
                        voice=os.getenv("OPENAI_REALTIME_VOICE", "marin"),
                    ),
                ),
                tools=local_tools.schemas(),
                tool_choice="auto",
                max_output_tokens=512,
            ),
        ),
    )

    transport = LocalAudioTransport(
        params=LocalAudioTransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_out_sample_rate=24000,
            audio_in_sample_rate=24000,
            input_device_index=1,  # Microphone device
        )
    )

    pipeline = Pipeline([
        transport.input(),
        realtime,
        transport.output(),
    ])

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
        ),
    )

    reminder_task = asyncio.create_task(reminder_loop(realtime, reminder_manager))
    runner = PipelineRunner()
    try:
        await runner.run(task)
    finally:
        logger.debug("Stopping Riko Assistant cleanup")
        local_tools.player.stop()
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
