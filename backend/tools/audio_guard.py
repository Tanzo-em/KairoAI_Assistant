import re
import time
from collections import deque
from loguru import logger

_recent_bot_texts = deque(maxlen=10)


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
    _recent_bot_texts.append((cleaned, expires_at))

    logger.debug(f"AUDIO GUARD REMEMBER BOT TTS: {cleaned}")


def is_probably_bot_echo(user_text: str) -> bool:
    now = time.time()
    cleaned_user = clean_text(user_text)

    if not cleaned_user:
        return False

    # remove expired bot texts
    while _recent_bot_texts and _recent_bot_texts[0][1] < now:
        _recent_bot_texts.popleft()

    user_words = set(cleaned_user.split())

    if not user_words:
        return False

    for bot_text, expires_at in list(_recent_bot_texts):
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