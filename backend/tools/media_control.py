import re

from loguru import logger

from pipecat.frames.frames import Frame, TranscriptionFrame, TTSTextFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection

from tools.mpv_player import MPVPlayer


class MediaCommandProcessor(FrameProcessor):
    DEFAULT_MUSIC_QUERY = "english language pop hits playlist usa uk songs "
    PAUSE_PHRASES = {
        "pause",
        "pause music",
        "pause the music",
        "pause song",
        "pause the song",
        "pause track",
        "pause it",
        "pause playback",
        "hold on",
        "hold the music",
        "wait",
    }
    RESUME_PHRASES = {
        "play",
        "resume",
        "resume music",
        "resume the music",
        "resume song",
        "resume it",
        "continue",
        "continue music",
        "continue playing",
        "continue it",
        "keep playing",
        "carry on",
        "go on",
        "unpause",
        "play again",
        "start again",
    }
    NEXT_PHRASES = {
        "next",
        "next song",
        "next track",
        "next music",
        "skip",
        "skip song",
        "skip this song",
        "skip track",
        "skip this track",
        "skip it",
        "skip music",
        "skip ahead",
        "next one",
        "play next",
        "play next song",
        "play the next song",
        "play the next one",
    }
    PREVIOUS_PHRASES = {
        "previous",
        "prev",
        "previous song",
        "prev song",
        "previous track",
        "prev track",
        "last song",
        "last track",
        "previous one",
        "last one",
        "go back",
        "back",
        "play previous",
        "play previous song",
        "play the previous song",
        "play last song",
        "play the last song",
        "play the previous one",
        "play the last one",
    }
    STOP_PHRASES = {
        "stop",
        "stop music",
        "stop the music",
        "stop song",
        "stop the song",
        "stop it",
        "stop playing",
        "quit music",
        "quit song",
        "turn off music",
        "turn off the music",
        "end music",
        "end song",
        "cancel music",
        "cancel song",
        "shut off music",
        "close music",
    }
    VOLUME_UP_PHRASES = {
        "volume up",
        "turn volume up",
        "turn up volume",
        "turn up the volume",
        "turn it up",
        "turn the music up",
        "turn sound up",
        "turn up sound",
        "raise volume",
        "raise the volume",
        "raise sound",
        "increase volume",
        "increase the volume",
        "increase sound",
        "make it louder",
        "louder",
        "boost volume",
    }
    VOLUME_DOWN_PHRASES = {
        "volume down",
        "turn volume down",
        "turn down volume",
        "turn down the volume",
        "turn it down",
        "turn the music down",
        "turn sound down",
        "turn down sound",
        "lower volume",
        "lower the volume",
        "lower sound",
        "decrease volume",
        "decrease the volume",
        "decrease sound",
        "reduce volume",
        "make it quieter",
        "quieter",
        "softer",
    }
    MUTE_PHRASES = {
        "mute",
        "mute music",
        "mute the music",
        "mute volume",
        "sound off",
    }
    UNMUTE_PHRASES = {
        "unmute",
        "unmute music",
        "unmute the music",
        "sound on",
    }
    PLAY_INTENT_PHRASES = (
        "play",
        "put on",
        "put music on",
        "put the music on",
        "put some music on",
        "put a song on",
        "start playing",
        "start music",
        "start the music",
        "start song",
        "start the song",
        "start track",
        "start the track",
        "stream",
        "listen to",
        "let me hear",
        "i want to hear",
        "i wanna hear",
        "i want to listen to",
        "find and play",
        "search and play",
    )
    GENERIC_MUSIC_QUERIES = {
        "",
        "a",
        "the",
        "some",
        "any",
        "something",
        "anything",
        "whatever",
        "random",
        "randomly",
        "video",
        "videos",
        "track",
        "tracks",
        "a track",
        "any track",
        "some track",
        "music",
        "some music",
        "any music",
        "random music",
        "song",
        "songs",
        "a song",
        "any song",
        "some song",
        "some songs",
        "random song",
        "random songs",
    }

    def __init__(self):
        super().__init__()
        self.player = MPVPlayer()
        self.awaiting_music_query = False

    def clean_text(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def strip_request_words(self, text: str) -> str:
        text = self.clean_text(text)

        prefixes = (
            "please",
            "can you",
            "could you",
            "would you",
            "will you",
            "would you please",
            "can you please",
            "could you please",
            "hey",
            "ok",
            "okay",
            "riko",
        )
        suffixes = (
            "please",
            "for me",
            "for us",
            "right now",
            "now",
        )

        changed = True
        while changed:
            changed = False
            for prefix in sorted(prefixes, key=len, reverse=True):
                if text == prefix:
                    return ""
                if text.startswith(prefix + " "):
                    text = text[len(prefix) :].strip()
                    changed = True

            for suffix in sorted(suffixes, key=len, reverse=True):
                if text == suffix:
                    return ""
                if text.endswith(" " + suffix):
                    text = text[: -len(suffix)].strip()
                    changed = True

        return text

    def has_phrase(self, text: str, phrases: set[str]) -> bool:
        return any(re.search(rf"\b{re.escape(phrase)}\b", text) for phrase in phrases)

    def extract_music_query(self, text: str) -> str:
        query = self.strip_request_words(text)

        leading_patterns = [
            r"^(?:i want to|i wanna|i would like to)\s+(?:listen to|hear|play)\s+",
            r"^(?:let me|lets)\s+(?:listen to|hear)\s+",
            r"^(?:find and play|search and play)\s+",
            r"^(?:find|search for|look up)\s+",
            r"^put\s+(?:some\s+|any\s+|the\s+|a\s+)?(?:music|songs|song|track|tracks)\s+on\s*",
            r"^(?:play|put on|start playing|start|stream)\s+(?:the\s+)?(?:music|songs|song|track|tracks)\s+(?:called|named|by|from)\s+",
            r"^(?:play|put on|start playing|start|stream)\s+(?:the\s+)?(?:song|track)\s+",
            r"^(?:play|put on|start playing|start|stream|listen to|hear)\s+",
        ]

        changed = True
        while changed:
            changed = False
            for pattern in leading_patterns:
                next_query = re.sub(pattern, "", query).strip()
                if next_query != query:
                    query = next_query
                    changed = True

        trailing_patterns = [
            r"\s+(?:on|from|in)\s+youtube$",
            r"\s+(?:on|from|in)\s+spotify$",
            r"\s+(?:on|from|in)\s+music$",
            r"\s+please$",
            r"\s+for me$",
        ]

        for pattern in trailing_patterns:
            query = re.sub(pattern, "", query).strip()

        query = " ".join(query.split())
        return query.strip()

    def is_generic_music_query(self, query: str) -> bool:
        return query.strip() in self.GENERIC_MUSIC_QUERIES

    def is_default_music_request(self, text: str) -> bool:
        text = self.clean_text(text)
        command_text = self.strip_request_words(text)

        if command_text == "play":
            return False

        return self.has_play_intent(text) and self.is_generic_music_query(self.extract_music_query(text))

    def has_play_intent(self, text: str) -> bool:
        text = self.clean_text(text)

        if self.get_playback_control_command(text):
            return False

        return any(re.search(rf"\b{re.escape(phrase)}\b", text) for phrase in self.PLAY_INTENT_PHRASES)

    def is_music_play_request(self, text: str) -> bool:
        text = self.clean_text(text)

        if self.is_default_music_request(text):
            return True

        if not self.has_play_intent(text):
            return False

        query = self.extract_music_query(text)
        return not self.is_generic_music_query(query)

    def is_media_command(self, text: str) -> bool:
        return self.is_music_play_request(text) or self.is_playback_control_command(text)

    def is_stop_command(self, text: str) -> bool:
        return self.get_playback_control_command(text) == "stop"

    def get_playback_control_command(self, text: str) -> str | None:
        text = self.clean_text(text)
        command_text = self.strip_request_words(text)

        exact_commands = [
            ("pause", self.PAUSE_PHRASES),
            ("resume", self.RESUME_PHRASES),
            ("next", self.NEXT_PHRASES),
            ("previous", self.PREVIOUS_PHRASES),
            ("stop", self.STOP_PHRASES),
            ("volume_up", self.VOLUME_UP_PHRASES),
            ("volume_down", self.VOLUME_DOWN_PHRASES),
            ("mute", self.MUTE_PHRASES),
            ("unmute", self.UNMUTE_PHRASES),
        ]

        for command, phrases in exact_commands:
            if command_text in phrases:
                return command

        phrase_commands = [
            ("unmute", self.UNMUTE_PHRASES),
            ("mute", self.MUTE_PHRASES),
            ("volume_up", self.VOLUME_UP_PHRASES),
            ("volume_down", self.VOLUME_DOWN_PHRASES),
            ("previous", self.PREVIOUS_PHRASES),
            ("next", self.NEXT_PHRASES),
            ("pause", self.PAUSE_PHRASES),
            ("stop", self.STOP_PHRASES),
        ]

        for command, phrases in phrase_commands:
            multi_word_phrases = {phrase for phrase in phrases if " " in phrase}
            if self.has_phrase(command_text, multi_word_phrases):
                return command

        if command_text in self.RESUME_PHRASES:
            return "resume"

        return None

    def is_playback_control_command(self, text: str) -> bool:
        return self.get_playback_control_command(text) is not None

    def should_speak_response(self, response: str) -> bool:
        silent_success_responses = {
            "Paused",
            "Playing",
            "Playing previous song",
            "Toggled playback",
            "Volume increased",
            "Volume decreased",
            "Muted",
            "Unmuted",
        }

        return response not in silent_success_responses and not response.startswith("Playing ")

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if not isinstance(frame, TranscriptionFrame):
            if (
                isinstance(frame, TTSTextFrame)
                and getattr(frame, "aggregated_by", None) == "wake_greeting"
                and self.player.is_audible()
            ):
                logger.info("SUPPRESSED WAKE GREETING DURING MPV PLAYBACK")
                self.player.restore_volume()
                return

            await self.push_frame(frame, direction)
            return

        original_text = frame.text.strip()
        text = self.clean_text(original_text)
        wake_activated = bool(frame.metadata.get("wake_activated", False))

        if self.player.is_audible():
            if not wake_activated:
                logger.info(f"IGNORED NON-WAKE TRANSCRIPTION DURING MPV PLAYBACK: {original_text}")
                return

            if not self.player.is_ducked():
                self.player.duck(duration_sec=6.0)

            if not self.is_media_command(text):
                logger.info(f"ALLOWING WAKE-ACTIVATED NON-MEDIA COMMAND DURING MPV PLAYBACK: {original_text}")
                await self.push_frame(frame, direction)
                return

        command = self.get_playback_control_command(text)

        if self.awaiting_music_query and command is None:
            query = self.extract_music_query(text)

            if self.is_generic_music_query(query):
                response = "Tell me the full song name or artist."
                await self.push_frame(
                    TTSTextFrame(
                        text=response,
                        aggregated_by="media_control",
                    ),
                    direction,
                )
                return

            self.awaiting_music_query = False
            response = self.player.play_search(query)
            await self.push_frame(
                TTSTextFrame(
                    text=response,
                    aggregated_by="media_control",
                ),
                direction,
            )
            return

        if not self.is_media_command(text):
            await self.push_frame(frame, direction)
            return

        logger.info(f"MPV MEDIA COMMAND: {original_text}")

        response = None

        if command == "pause":
            response = self.player.pause()

        elif command == "resume":
            response = self.player.play()
            if response.startswith("Tell me"):
                self.awaiting_music_query = True

        elif command == "next":
            response = self.player.next()

        elif command == "previous":
            response = self.player.previous()

        elif command == "stop":
            self.awaiting_music_query = False
            response = self.player.stop()

        elif command == "volume_up":
            response = self.player.volume_up()

        elif command == "volume_down":
            response = self.player.volume_down()

        elif command == "mute":
            response = self.player.mute()

        elif command == "unmute":
            response = self.player.unmute()

        elif self.is_music_play_request(text):
            query = self.extract_music_query(text)

            if self.is_default_music_request(text):
                self.awaiting_music_query = False
                response = self.player.play_default_music()
            elif self.is_generic_music_query(query):
                self.awaiting_music_query = True
                response = "Tell me the full song name or artist."
            else:
                self.awaiting_music_query = False
                response = self.player.play_search(query)

        if response:
            if self.player.is_audible():
                self.player.restore_volume()

            if not self.should_speak_response(response):
                logger.info(f"SUPPRESSED SPOKEN MEDIA ACK DURING PLAYBACK: {response}")
                return

            await self.push_frame(
                TTSTextFrame(
                    text=response,
                    aggregated_by="media_control",
                ),
                direction,
            )
            return

        await self.push_frame(frame, direction)
