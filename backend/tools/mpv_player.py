import os
import signal
import subprocess
from loguru import logger


class MPVPlayer:
    def __init__(self):
        self.process = None

    def stop_existing(self):
        if self.process and self.process.poll() is None:
            logger.info("Stopping existing mpv playback")
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                try:
                    os.kill(self.process.pid, signal.SIGKILL)
                except Exception:
                    pass

        self.process = None

    def get_audio_url(self, query: str) -> str | None:
        query = query.strip()

        if not query:
            return None

        logger.info(f"Getting YouTube audio URL for: {query}")

        try:
            result = subprocess.run(
                [
                    "/home/tanzo/Kyron_automation/KairoAI-Assistant/backend/.venv/bin/yt-dlp",
                    "-f",
                    "bestaudio",
                    "-g",
                    f"ytsearch1:{query}",
                ],
                capture_output=True,
                text=True,
                timeout=20,
            )

            if result.returncode != 0:
                logger.error(f"yt-dlp error: {result.stderr.strip()}")
                return None

            url = result.stdout.strip().splitlines()[0] if result.stdout.strip() else None
            return url

        except Exception as e:
            logger.error(f"Failed to get audio URL: {e}")
            return None

    def play_search(self, query: str):
        self.stop_existing()

        audio_url = self.get_audio_url(query)

        if not audio_url:
            return "I could not find that song."

        logger.info(f"Playing with mpv: {query}")

        self.process = subprocess.Popen(
            [
                "mpv",
                "--no-video",
                "--no-terminal",
                "--force-window=no",
                audio_url,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        return f"Playing {query}"

    def pause(self):
        subprocess.run(
            ["playerctl", "pause"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return "Paused"

    def play(self):
        subprocess.run(
            ["playerctl", "play"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return "Playing"

    def play_pause(self):
        subprocess.run(
            ["playerctl", "play-pause"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return "Toggled playback"

    def stop(self):
        self.stop_existing()
        return "Stopped"

    def volume_up(self):
        subprocess.run(
            ["playerctl", "volume", "0.1+"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return "Volume increased"

    def volume_down(self):
        subprocess.run(
            ["playerctl", "volume", "0.1-"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return "Volume decreased"