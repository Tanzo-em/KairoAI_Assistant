import asyncio
import json
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from loguru import logger
from pipecat.frames.frames import LLMFullResponseStartFrame
from pipecat.services.openai.realtime import events
from pipecat.services.openai.realtime.llm import OpenAIRealtimeLLMService

from tools.mpv_player import MPVPlayer
from tools.reminder_manager import ReminderManager
from tools.ui_state import set_ui_status
from tools.web_search import ask_with_web_search


WAKE_WORD_ALIASES = (
    "riko",
    "rico",
    "ricko",
    "rikko",
    "reeko",
    "reico",
    "reiko",
    "ryko",
    "riku",
    "biko",
    "viko",
)
WAKE_WORD_PATTERN = "|".join(re.escape(alias) for alias in WAKE_WORD_ALIASES)


class RealtimeLocalTools:
    def __init__(self, reminder_manager: ReminderManager):
        self.player = MPVPlayer()
        self.reminder_manager = reminder_manager

    def schemas(self) -> list[dict]:
        return [
            {
                "type": "function",
                "name": "control_media",
                "description": "Control local music playback or play a requested song/artist.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": [
                                "play",
                                "pause",
                                "resume",
                                "next",
                                "previous",
                                "stop",
                                "volume_up",
                                "volume_down",
                                "mute",
                                "unmute",
                            ],
                        },
                        "query": {
                            "type": "string",
                            "description": "Song, artist, album, or playlist to play. Required for play when specific music is requested.",
                        },
                    },
                    "required": ["action"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "set_reminder",
                "description": "Set an alarm or reminder from the user's original spoken request.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "request": {
                            "type": "string",
                            "description": "The user's complete reminder or alarm request, including time and message.",
                        }
                    },
                    "required": ["request"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "get_current_info",
                "description": "Get current information such as weather, news, scores, prices, availability, or local time in another city.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "A concise search-style version of the user's current information request.",
                        }
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "get_local_datetime",
                "description": "Get Riko's current local date and time.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
        ]

    async def call(self, name: str, arguments: dict) -> str:
        if name == "control_media":
            result = await asyncio.to_thread(self._control_media, arguments)
            await self._publish_media_status(arguments, result)
            return result
        if name == "set_reminder":
            return await asyncio.to_thread(self._set_reminder, arguments)
        if name == "get_current_info":
            return await asyncio.to_thread(self._get_current_info, arguments)
        if name == "get_local_datetime":
            return self._get_local_datetime()

        return f"Unknown tool: {name}"

    async def _publish_media_status(self, arguments: dict, result: str):
        action = str(arguments.get("action", "")).strip().lower()
        result_text = result.strip()

        if result_text.lower().startswith("playing"):
            await set_ui_status("playing", result_text)
            return

        if action == "pause":
            await set_ui_status("listening", "Music paused")
            return

        if action == "stop":
            await set_ui_status("listening", "Music stopped")

    def _control_media(self, arguments: dict) -> str:
        action = str(arguments.get("action", "")).strip().lower()
        query = str(arguments.get("query", "")).strip()

        if action == "play":
            return self.player.play_search(query) if query else self.player.play_default_music()
        if action == "pause":
            return self.player.pause()
        if action == "resume":
            return self.player.play()
        if action == "next":
            return self.player.next()
        if action == "previous":
            return self.player.previous()
        if action == "stop":
            return self.player.stop()
        if action == "volume_up":
            return self.player.volume_up()
        if action == "volume_down":
            return self.player.volume_down()
        if action == "mute":
            return self.player.mute()
        if action == "unmute":
            return self.player.unmute()

        return "Unknown media action."

    def _set_reminder(self, arguments: dict) -> str:
        request = str(arguments.get("request", "")).strip()
        parsed = self.reminder_manager.parse_command(request)

        if not parsed:
            return (
                "I could not understand the reminder time. Ask the user to try a phrase like "
                "set alarm in 30 seconds, or remind me at 3:30 PM to call customer."
            )

        self.reminder_manager.add(
            remind_at=parsed["time"],
            message=parsed["message"],
            kind=parsed["kind"],
        )

        time_text = parsed["time"].strftime("%I:%M %p")
        if parsed["kind"] == "alarm":
            return f"Alarm set for {time_text}."

        return f"Reminder set for {time_text}: {parsed['message']}."

    def _get_current_info(self, arguments: dict) -> str:
        query = str(arguments.get("query", "")).strip()
        if not query:
            return "I need a specific current information query."

        return ask_with_web_search(
            f"{query}\n\n"
            "Use current web results. Answer briefly and naturally for spoken voice output. "
            "Do not include source names, citations, URLs, domains, or links."
        )

    def _get_local_datetime(self) -> str:
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        return now.strftime("%A, %d %B %Y, %I:%M:%S %p, Asia/Kolkata")


class OpenAIRealtime2Service(OpenAIRealtimeLLMService):
    """Realtime service with local function tools and Realtime-owned speech turn handling."""

    def __init__(self, *, local_tools: RealtimeLocalTools, **kwargs):
        super().__init__(**kwargs)
        self.local_tools = local_tools
        self._bot_speaking_until = 0.0

    async def _handle_evt_speech_started(self, evt):
        self.local_tools.player.duck(duration_sec=6.0)
        await self.start_processing_metrics()

    async def _handle_evt_audio_delta(self, evt):
        self._bot_speaking_until = time.time() + 2.0
        await super()._handle_evt_audio_delta(evt)

    async def _handle_evt_audio_done(self, evt):
        self._bot_speaking_until = time.time() + 2.0
        await super()._handle_evt_audio_done(evt)

    async def handle_evt_input_audio_transcription_completed(self, evt):
        transcript = (evt.transcript or "").strip()
        decision = self._gate_transcript(transcript)

        if decision.get("interrupt"):
            logger.info(f"REALTIME INTERRUPTING BOT: transcript={transcript!r}")
            await self._handle_interruption()
            self._bot_speaking_until = 0.0

        if not decision["allowed"]:
            logger.info(f"REALTIME GATE IGNORED: {decision['reason']} transcript={transcript!r}")
            await self._delete_conversation_item(evt.item_id)
            return

        if decision["text"] != transcript:
            await self._delete_conversation_item(evt.item_id)
            await self._create_user_text_item(decision["text"])

        logger.info(f"REALTIME GATE ACCEPTED: {decision['reason']} transcript={transcript!r}")
        await self._create_response()

    def _gate_transcript(self, transcript: str) -> dict:
        if not transcript:
            return {"allowed": False, "reason": "empty_transcript", "text": "", "interrupt": False}

        stripped = self._strip_wake_phrase(transcript)
        has_wake = stripped != transcript.strip()

        if self._is_transcription_prompt_leak(stripped):
            return {
                "allowed": False,
                "reason": "transcription_prompt_leak",
                "text": "",
                "interrupt": False,
            }

        if self._is_bot_speaking():
            if not has_wake:
                return {
                    "allowed": False,
                    "reason": "bot_speaking",
                    "text": transcript,
                    "interrupt": False,
                }

            if not stripped:
                return {
                    "allowed": False,
                    "reason": "wake_interrupted_bot",
                    "text": "",
                    "interrupt": True,
                }

            return {
                "allowed": True,
                "reason": "wake_interruption_command",
                "text": stripped,
                "interrupt": True,
            }

        if self.local_tools.player.is_audible() and not has_wake:
            return {
                "allowed": False,
                "reason": "music_playing_without_wake",
                "text": transcript,
                "interrupt": False,
            }

        text = stripped if has_wake else transcript
        if not text:
            return {"allowed": False, "reason": "wake_only", "text": "", "interrupt": False}

        reason = "wake_command" if has_wake else "normal_turn"
        return {"allowed": True, "reason": reason, "text": text, "interrupt": False}

    def _strip_wake_phrase(self, transcript: str) -> str:
        text = transcript.strip()
        text = re.sub(
            rf"^\s*(?:hey\s+|hello\s+|ok\s+|okay\s+)?(?:{WAKE_WORD_PATTERN})[\s,.:;!?-]*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        return text.strip()

    def _is_transcription_prompt_leak(self, text: str) -> bool:
        normalized = re.sub(r"[^a-z0-9\s]", " ", text.lower())
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized in {
            "voice assistant commands reminders alarms media controls weather news and current information",
            "riko voice assistant commands reminders alarms media controls weather news and current information",
        }

    def _is_bot_speaking(self) -> bool:
        return time.time() < self._bot_speaking_until

    async def _delete_conversation_item(self, item_id: str):
        if not item_id:
            return

        try:
            await self.send_client_event(events.ConversationItemDeleteEvent(item_id=item_id))
        except Exception as e:
            logger.debug(f"Could not delete gated realtime item {item_id}: {e}")

    async def _create_user_text_item(self, text: str):
        item = events.ConversationItem(
            type="message",
            role="user",
            content=[events.ItemContent(type="input_text", text=text)],
        )
        await self.send_client_event(events.ConversationItemCreateEvent(item=item))

    async def _handle_evt_function_call_arguments_done(self, evt):
        try:
            arguments = json.loads(evt.arguments or "{}")
        except json.JSONDecodeError:
            arguments = {}

        function_call_item = self._pending_function_calls.pop(evt.call_id, None)
        function_name = getattr(function_call_item, "name", None)

        if not function_name:
            logger.warning(f"Realtime function call missing name for call_id={evt.call_id}")
            return

        logger.info(f"REALTIME TOOL CALL: {function_name} {arguments}")
        result = await self.local_tools.call(function_name, arguments)
        logger.info(f"REALTIME TOOL RESULT: {result}")

        await self._send_tool_result(evt.call_id, result)
        await self._create_response()

    async def _create_response(self):
        if not await self._wait_for_api_session_ready():
            logger.warning("Realtime session is not ready; response.create skipped")
            return

        await self.push_frame(LLMFullResponseStartFrame())
        await self.start_processing_metrics()
        await self.start_ttfb_metrics()
        await self.send_client_event(
            events.ResponseCreateEvent(
                response=events.ResponseProperties(output_modalities=["audio"])
            )
        )

    async def _send_tool_result(self, tool_call_id: str, result: str):
        item = events.ConversationItem(
            type="function_call_output",
            call_id=tool_call_id,
            output=result,
        )
        await self.send_client_event(events.ConversationItemCreateEvent(item=item))

    async def speak_text(self, text: str):
        text = text.strip()
        if not text:
            return

        if not await self._wait_for_api_session_ready():
            logger.warning("Realtime session is not ready; speech skipped")
            return

        await self._ws_send(
            {
                "type": "response.create",
                "response": {
                    "conversation": "none",
                    "output_modalities": ["audio"],
                    "input": [
                        {
                            "type": "message",
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": (
                                        "Read the following assistant message aloud exactly, "
                                        "without adding or changing words:\n"
                                        f"{text}"
                                    ),
                                }
                            ],
                        }
                    ],
                    "instructions": (
                        "Speak only the provided assistant message exactly. "
                        "Do not add prefaces, explanations, or extra words."
                    ),
                },
            }
        )

    async def _wait_for_api_session_ready(self, timeout_sec: float = 5.0) -> bool:
        deadline = time.time() + timeout_sec
        while not self._api_session_ready and time.time() < deadline:
            await asyncio.sleep(0.05)
        return self._api_session_ready
