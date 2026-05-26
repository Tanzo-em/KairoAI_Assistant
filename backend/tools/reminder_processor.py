from loguru import logger

from pipecat.frames.frames import Frame, TranscriptionFrame, TTSTextFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection

from tools.reminder_manager import ReminderManager


class ReminderProcessor(FrameProcessor):
    def __init__(self, reminder_manager: ReminderManager):
        super().__init__()
        self.reminder_manager = reminder_manager

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if not isinstance(frame, TranscriptionFrame):
            await self.push_frame(frame, direction)
            return

        original_text = frame.text.strip()
        try:
            parsed = self.reminder_manager.parse_command(original_text)
        except Exception as e:
            logger.error(f"REMINDER PARSE FAILED: {original_text}: {e}")
            parsed = None

        if not parsed:
            if self.reminder_manager.looks_like_reminder_command(original_text):
                await self.push_frame(
                    TTSTextFrame(
                        text="I heard the alarm or reminder request, but I could not understand the time. Try saying, set alarm in 30 seconds, or set alarm for 3:30 PM.",
                        aggregated_by="reminder_processor",
                    ),
                    direction,
                )
                return

            await self.push_frame(frame, direction)
            return

        self.reminder_manager.add(
            remind_at=parsed["time"],
            message=parsed["message"],
            kind=parsed["kind"],
        )

        time_text = parsed["time"].strftime("%I:%M %p")

        if parsed["kind"] == "alarm":
            response = f"Alarm set for {time_text}."
        else:
            response = f"Reminder set for {time_text}: {parsed['message']}."

        logger.info(f"REMINDER HANDLED: {original_text}")
        await self.push_frame(
            TTSTextFrame(
                text=response,
                aggregated_by="reminder_processor",
            ),
            direction,
        )
