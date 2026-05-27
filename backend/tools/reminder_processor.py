import asyncio

from loguru import logger

from pipecat.frames.frames import Frame, TranscriptionFrame, TTSTextFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection

from tools.reminder_manager import ReminderManager


class ReminderProcessor(FrameProcessor):
    def __init__(self, reminder_manager: ReminderManager):
        super().__init__()
        self.reminder_manager = reminder_manager
        self.pending_alarm_prefix = None
        self.pending_alarm_fragments = []
        self.pending_alarm_task = None
        self.pending_direction = None

    def is_partial_alarm_command(self, text: str) -> bool:
        cleaned = self.reminder_manager._normalize_spoken_time(text.lower().strip())
        return bool(
            cleaned in {
                "set alarm for",
                "set an alarm for",
                "set the alarm for",
                "set alarm at",
                "set an alarm at",
                "set the alarm at",
            }
        )

    def is_short_time_fragment(self, text: str) -> bool:
        cleaned = self.reminder_manager._normalize_spoken_time(text.lower().strip())
        return bool(cleaned and len(cleaned.split()) <= 4 and not self.reminder_manager.looks_like_reminder_command(cleaned))

    def cancel_pending_alarm_task(self):
        if self.pending_alarm_task and not self.pending_alarm_task.done():
            self.pending_alarm_task.cancel()
        self.pending_alarm_task = None

    async def finalize_pending_alarm(self):
        await asyncio.sleep(1.1)

        if not self.pending_alarm_prefix or not self.pending_alarm_fragments:
            return

        text = " ".join([self.pending_alarm_prefix, *self.pending_alarm_fragments])
        direction = self.pending_direction
        self.pending_alarm_prefix = None
        self.pending_alarm_fragments = []
        self.pending_alarm_task = None
        self.pending_direction = None

        logger.info(f"FINALIZING SPLIT ALARM COMMAND: {text}")
        await self.handle_reminder_text(text, direction)

    async def handle_reminder_text(self, original_text: str, direction: FrameDirection):
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
                return True

            return False

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
        return True

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if not isinstance(frame, TranscriptionFrame):
            await self.push_frame(frame, direction)
            return

        original_text = frame.text.strip()

        if self.pending_alarm_prefix and self.is_short_time_fragment(original_text):
            self.pending_alarm_fragments.append(original_text)
            self.pending_direction = direction
            self.cancel_pending_alarm_task()
            self.pending_alarm_task = asyncio.create_task(self.finalize_pending_alarm())
            logger.info(f"COLLECTED SPLIT ALARM FRAGMENT: {original_text}")
            return

        if self.is_partial_alarm_command(original_text):
            self.pending_alarm_prefix = original_text
            self.pending_alarm_fragments = []
            self.pending_direction = direction
            self.cancel_pending_alarm_task()
            self.pending_alarm_task = asyncio.create_task(self.finalize_pending_alarm())
            logger.info(f"STARTED SPLIT ALARM COMMAND: {original_text}")
            return

        self.cancel_pending_alarm_task()
        handled = await self.handle_reminder_text(original_text, direction)

        if not handled:
            await self.push_frame(frame, direction)
