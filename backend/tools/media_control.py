from loguru import logger

from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection

from tools.mpv_player import MPVPlayer


class MediaCommandProcessor(FrameProcessor):
    def __init__(self):
        super().__init__()
        self.player = MPVPlayer()

    def clean_text(self, text: str) -> str:
        return text.lower().strip()

    def extract_music_query(self, text: str) -> str:
        text = text.lower()

        remove_phrases = [
            "echo",
            "play",
            "play music",
            "play song",
            "play the song",
            "on youtube",
            "youtube",
            "music",
            "song",
        ]

        query = text

        for phrase in remove_phrases:
            query = query.replace(phrase, " ")

        query = " ".join(query.split())
        return query.strip()

    def is_media_command(self, text: str) -> bool:
        media_words = [
            "play",
            "pause",
            "resume",
            "stop music",
            "stop song",
            "stop playing",
            "volume up",
            "volume down",
            "increase volume",
            "decrease volume",
        ]

        return any(word in text for word in media_words)

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if not isinstance(frame, TranscriptionFrame):
            await self.push_frame(frame, direction)
            return

        original_text = frame.text.strip()
        text = self.clean_text(original_text)

        if not self.is_media_command(text):
            await self.push_frame(frame, direction)
            return

        logger.info(f"MPV MEDIA COMMAND: {original_text}")

        response = None

        if "pause" in text:
            response = self.player.pause()

        elif "resume" in text:
            response = self.player.play()

        elif text == "play":
            response = self.player.play()

        elif "stop music" in text or "stop song" in text or "stop playing" in text:
            response = self.player.stop()

        elif "volume up" in text or "increase volume" in text:
            response = self.player.volume_up()

        elif "volume down" in text or "decrease volume" in text:
            response = self.player.volume_down()

        elif "play" in text:
            query = self.extract_music_query(text)

            if not query:
                response = "Please tell me what to play."
            else:
                response = self.player.play_search(query)

        if response:
            frame.text = response
            await self.push_frame(frame, direction)
            return

        await self.push_frame(frame, direction)