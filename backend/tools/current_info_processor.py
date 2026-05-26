# function for voiceassistant to do quick web search for current affairs
import asyncio
import os
import re

from loguru import logger
from pipecat.frames.frames import Frame, TranscriptionFrame, TTSTextFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from tools.web_search import ask_with_web_search


class CurrentInfoProcessor(FrameProcessor):
    CURRENT_INFO_PATTERNS = (
        r"\bnews\b",
        r"\bheadlines?\b",
        r"\btop stories\b",
        r"\blatest\b",
        r"\bcurrent\b",
        r"\btoday\b",
        r"\bnow\b",
        r"\bright now\b",
        r"\bweather\b",
        r"\btemperature\b",
        r"\brain\b",
        r"\bscore\b",
        r"\bmatch\b",
        r"\bfixture\b",
        r"\bpoints table\b",
        r"\bprice\b",
        r"\bstock\b",
        r"\bcrypto\b",
        r"\bbitcoin\b",
        r"\bgold rate\b",
        r"\bexchange rate\b",
        r"\bavailable\b",
        r"\bnear me\b",
        r"\bopen now\b",
        r"\bresult\b",
        r"\bwho is the current\b",
    )

    def __init__(self):
        super().__init__()
        self.awaiting_city_for_time = False

    def clean_text(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def is_current_info_request(self, text: str) -> bool:
        cleaned = self.clean_text(text)
        return any(re.search(pattern, cleaned) for pattern in self.CURRENT_INFO_PATTERNS)

    def is_weather_request(self, text: str) -> bool:
        cleaned = self.clean_text(text)
        return any(word in cleaned for word in ["weather", "temperature", "rain"])

    def is_time_request(self, text: str) -> bool:
        cleaned = self.clean_text(text)
        return bool(
            re.search(r"\b(?:what(?:'s| is)?|tell me|give me|show me)\s+(?:the\s+)?(?:current\s+)?time\b", cleaned)
            or re.search(r"\b(?:current\s+)?time\s+(?:now|right now|today)\b", cleaned)
            or cleaned in {"time", "current time", "what time", "what is the time", "whats the time"}
        )

    def has_location(self, text: str) -> bool:
        cleaned = self.clean_text(text)
        return bool(
            re.search(r"\b(?:in|at|for|near)\s+[a-z][a-z\s]+", cleaned)
            or "near me" in cleaned
        )

    def default_location(self) -> str | None:
        return (
            os.getenv("ASSISTANT_LOCATION")
            or os.getenv("WEATHER_LOCATION")
            or os.getenv("DEFAULT_LOCATION")
        )

    def build_query(self, text: str) -> str:
        cleaned = self.clean_text(text)

        if "news" in cleaned or "headline" in cleaned or "top stories" in cleaned:
            count = 3 if re.search(r"\btop\s+3\b|\bthree\b", cleaned) else 5
            return (
                f"{text}\n\n"
                f"Use current web results. Give exactly {count} major news items. "
                "Each item must be one short spoken sentence on its own line. "
                "Do not include source names, citations, URLs, domains, or links."
            )

        if self.is_weather_request(text):
            location = self.default_location()

            if not self.has_location(text) and location:
                text = f"{text} in {location}"

            location_rule = (
                f"Use {location} as the user's default location when no location is stated. "
                if location
                else "If no location is stated, ask which city to use instead of guessing. "
            )

            return (
                f"{text}\n\n"
                "Use current web results for weather. "
                f"{location_rule}"
                "Answer with current conditions and today's high and low if available. "
                "Keep it to one or two short spoken sentences. "
                "Do not include source names, citations, URLs, domains, or links."
            )

        return (
            f"{text}\n\n"
            "Use current web results. Answer briefly and directly for a voice assistant. "
            "Mention the most relevant current detail first. "
            "Do not include source names, citations, URLs, domains, or links."
        )

    def build_time_query(self, city: str) -> str:
        return (
            f"What is the current local time in {city}?\n\n"
            "Use current web results if needed. Answer with only the city name, "
            "the current local time, and the day/date. Keep it to one short spoken sentence. "
            "Do not include source names, citations, URLs, domains, or links."
        )

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if not isinstance(frame, TranscriptionFrame):
            await self.push_frame(frame, direction)
            return

        original_text = frame.text.strip()

        if self.awaiting_city_for_time:
            self.awaiting_city_for_time = False
            city = self.clean_text(original_text)

            if not city:
                await self.push_frame(
                    TTSTextFrame(
                        text="Which city are you currently in?",
                        aggregated_by="current_info_processor",
                    ),
                    direction,
                )
                return

            logger.info(f"CURRENT TIME CITY: {original_text}")

            try:
                answer = await asyncio.to_thread(
                    ask_with_web_search,
                    self.build_time_query(original_text),
                )
            except Exception as e:
                logger.error(f"Current time web search failed: {e}")
                answer = "I could not get the current time right now. Please check your internet or OpenAI API key."

            await self.push_frame(
                TTSTextFrame(
                    text=answer,
                    aggregated_by="current_info_processor",
                ),
                direction,
            )
            return

        if self.is_time_request(original_text) and not self.has_location(original_text):
            self.awaiting_city_for_time = True
            await self.push_frame(
                TTSTextFrame(
                    text="Which city are you currently in?",
                    aggregated_by="current_info_processor",
                ),
                direction,
            )
            return

        if self.is_time_request(original_text) and self.has_location(original_text):
            logger.info(f"CURRENT TIME REQUEST: {original_text}")

            try:
                answer = await asyncio.to_thread(
                    ask_with_web_search,
                    self.build_time_query(original_text),
                )
            except Exception as e:
                logger.error(f"Current time web search failed: {e}")
                answer = "I could not get the current time right now. Please check your internet or OpenAI API key."

            await self.push_frame(
                TTSTextFrame(
                    text=answer,
                    aggregated_by="current_info_processor",
                ),
                direction,
            )
            return

        if not self.is_current_info_request(original_text):
            await self.push_frame(frame, direction)
            return

        logger.info(f"CURRENT INFO REQUEST: {original_text}")

        try:
            answer = await asyncio.to_thread(
                ask_with_web_search,
                self.build_query(original_text),
            )
        except Exception as e:
            logger.error(f"Current info web search failed: {e}")
            answer = "I could not get current information right now. Please check your internet or OpenAI API key."

        await self.push_frame(
            TTSTextFrame(
                text=answer,
                aggregated_by="current_info_processor",
            ),
            direction,
        )
