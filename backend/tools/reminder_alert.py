import os
import math
import struct
import tempfile
import wave
from pathlib import Path

from loguru import logger

from tools.audio_guard import remember_bot_tts
from tools.audio_playback import play_wav_interruptible
from tools.edge_tts import speak_with_edge_tts
from tools.gtts_tts import speak_with_gtts


def _write_alarm_wav(path: Path, *, repeats: int = 4) -> None:
    sample_rate = 24000
    tone_seconds = 0.35
    gap_seconds = 0.15
    frequency = 880
    amplitude = 26000

    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)

        for _ in range(repeats):
            for index in range(int(sample_rate * tone_seconds)):
                sample = int(
                    amplitude
                    * math.sin(2 * math.pi * frequency * index / sample_rate)
                )
                wav.writeframes(struct.pack("<h", sample))

            wav.writeframes(b"\x00\x00" * int(sample_rate * gap_seconds))


def _play_wav(path: Path) -> None:
    logger.info(f"Playing reminder alert WAV: {path}")
    if not play_wav_interruptible(path):
        raise RuntimeError("Reminder alert playback was interrupted")


async def play_alarm_sound() -> None:
    import asyncio

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        wav_path = Path(temp_file.name)

    try:
        _write_alarm_wav(wav_path)
        await asyncio.to_thread(_play_wav, wav_path)
    finally:
        wav_path.unlink(missing_ok=True)


async def speak_reminder_alert(text: str, *, kind: str = "reminder") -> None:
    sound_played = False
    remember_bot_tts(text, ttl_sec=20.0)

    if kind == "alarm":
        remember_bot_tts("Alarm ready", ttl_sec=20.0)
        remember_bot_tts("Your alarm is ready", ttl_sec=20.0)

    try:
        if kind == "alarm":
            for _ in range(3):
                await play_alarm_sound()
        else:
            await play_alarm_sound()
        sound_played = True
    except Exception as e:
        logger.error(f"Reminder alert beep failed: {e}")

    if os.getenv("USE_SHERPA", "0") == "1":
        try:
            from tools.sherpa_integration import (
                sherpa_installed,
                sherpa_models_present,
                speak_with_sherpa_tts,
            )

            if sherpa_installed() and sherpa_models_present():
                import asyncio

                await asyncio.to_thread(speak_with_sherpa_tts, text)
                logger.info("Reminder alert spoken with Sherpa TTS")
                return
        except Exception as e:
            logger.error(f"Reminder alert Sherpa TTS failed: {e}")
            if sound_played:
                return

    if os.getenv("USE_GTTTS", "0") == "1":
        try:
            await speak_with_gtts(text)
            logger.info("Reminder alert spoken with gTTS")
        except Exception as e:
            logger.error(f"Reminder alert gTTS failed: {e}")
            if not sound_played:
                raise
        return

    try:
        await speak_with_edge_tts(text)
        logger.info("Reminder alert spoken with Edge TTS")
    except Exception as e:
        logger.error(f"Reminder alert Edge TTS failed: {e}")
        try:
            await speak_with_gtts(text)
            logger.info("Reminder alert spoken with gTTS fallback")
        except Exception as e:
            logger.error(f"Reminder alert gTTS fallback failed: {e}")
            if not sound_played:
                raise
