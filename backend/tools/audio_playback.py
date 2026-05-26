import subprocess
import threading
import time
from pathlib import Path

from tools.audio_guard import mark_bot_speaking_end, mark_bot_speaking_start

_playback_lock = threading.RLock()
_stop_event = threading.Event()
_current_process: subprocess.Popen | None = None
_playback_generation = 0


def stop_current_playback() -> bool:
    global _playback_generation

    with _playback_lock:
        _playback_generation += 1
        _stop_event.set()
        process = _current_process
        if process and process.poll() is None:
            process.terminate()
            return True
    return False


def playback_generation() -> int:
    with _playback_lock:
        return _playback_generation


def was_playback_stopped_since(generation: int) -> bool:
    with _playback_lock:
        return _playback_generation != generation


def play_wav_interruptible(wav_path: Path, generation: int | None = None) -> bool:
    global _current_process

    with _playback_lock:
        if generation is not None and _playback_generation != generation:
            return False
        _stop_event.clear()

    mark_bot_speaking_start()
    process = subprocess.Popen(
        ["aplay", str(wav_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    with _playback_lock:
        _current_process = process

    try:
        while process.poll() is None:
            if _stop_event.is_set():
                process.terminate()
                try:
                    process.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=0.5)
                return False
            time.sleep(0.03)

        stderr = process.stderr.read() if process.stderr else ""
        if process.returncode != 0 and not _stop_event.is_set():
            raise RuntimeError(f"aplay failed: {stderr.strip()}")

        return not _stop_event.is_set()
    finally:
        with _playback_lock:
            if _current_process is process:
                _current_process = None
        mark_bot_speaking_end()
