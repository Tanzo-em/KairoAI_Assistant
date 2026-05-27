# it guard the Assistant to hear its own voice
import re
import time
from threading import RLock
from collections import deque
from loguru import logger

_recent_bot_texts = deque(maxlen=10)
_state_lock = RLock()
_speaking_count = 0
_speaking_until = 0.0


def clean_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def remember_bot_tts(text: str, ttl_sec: float = 8.0):
    cleaned = clean_text(text)

    if not cleaned:
        return

    expires_at = time.time() + ttl_sec
    with _state_lock:
        _recent_bot_texts.append((cleaned, expires_at))

    logger.debug(f"AUDIO GUARD REMEMBER BOT TTS: {cleaned}")


def mark_bot_speaking_start():
    global _speaking_count

    with _state_lock:
        _speaking_count += 1

    logger.debug("AUDIO GUARD BOT SPEAKING START")


def mark_bot_speaking_end(cooldown_sec: float = 1.2):
    global _speaking_count, _speaking_until

    with _state_lock:
        _speaking_count = max(0, _speaking_count - 1)
        _speaking_until = max(_speaking_until, time.time() + cooldown_sec)

    logger.debug(f"AUDIO GUARD BOT SPEAKING END cooldown={cooldown_sec:.2f}s")


def is_bot_speaking() -> bool:
    with _state_lock:
        return _speaking_count > 0 or time.time() < _speaking_until


def is_probably_bot_echo(user_text: str) -> bool:
    now = time.time()
    cleaned_user = clean_text(user_text)

    if not cleaned_user:
        return False

    user_command_prefixes = (
        "set alarm",
        "set an alarm",
        "set the alarm",
        "set reminder",
        "set a reminder",
        "remind me",
        "wake me",
    )

    if cleaned_user.startswith(user_command_prefixes):
        return False

    # remove expired bot texts
    with _state_lock:
        while _recent_bot_texts and _recent_bot_texts[0][1] < now:
            _recent_bot_texts.popleft()
        recent_bot_texts = list(_recent_bot_texts)

    user_words = set(cleaned_user.split())

    if not user_words:
        return False

    for bot_text, expires_at in recent_bot_texts:
        if expires_at < now:
            continue

        bot_words = set(bot_text.split())

        if not bot_words:
            continue

        # direct substring match
        if cleaned_user in bot_text or bot_text in cleaned_user:
            logger.debug(f"AUDIO GUARD MATCH SUBSTRING: user='{cleaned_user}' bot='{bot_text}'")
            return True

        # word-overlap match
        overlap = len(user_words.intersection(bot_words))
        ratio = overlap / max(1, min(len(user_words), len(bot_words)))

        if ratio >= 0.65 and overlap >= 2:
            logger.debug(
                f"AUDIO GUARD MATCH OVERLAP: ratio={ratio:.2f} user='{cleaned_user}' bot='{bot_text}'"
            )
            return True

    bot_substrings = {
        "i cant play music directly",
        "i cannot play music directly",
        "preferred music platform",
        "tell me the full song name or artist",
        "i couldnt find",
        "nothing is playing",
        "alarm ringing",
        "alarm ready",
        "your alarm is ready",
    }

    if any(phrase in cleaned_user for phrase in bot_substrings):
        logger.debug(f"AUDIO GUARD BOT SUBSTRING: {cleaned_user}")
        return True

    # common short bot phrases
    common_bot_phrases = {
        "hey",
        "how can i help you",
        "how can i help you today",
        "im here to help you",
        "i am here to help you",
        "got it",
        "great",
        "okay",
        "ok",
        "what do you need",
    }

    if cleaned_user in common_bot_phrases:
        logger.debug(f"AUDIO GUARD COMMON BOT PHRASE: {cleaned_user}")
        return True

    return False
