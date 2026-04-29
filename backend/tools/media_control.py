import webbrowser
import urllib.parse
import subprocess
from loguru import logger
from loguru import logger
from pipecat.frames.frames import Frame, TranscriptionFrame, TTSTextFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection


def open_url(url: str):
    try:
        subprocess.Popen(["xdg-open", url])
    except Exception:
        webbrowser.open(url)


def play_youtube(query: str) -> str:
    query = query.strip()

    if not query:
        open_url("https://www.youtube.com")
        return "Opening YouTube."

    try:
        import yt_dlp

        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "default_search": "ytsearch1",
            "noplaylist": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)

        if "entries" in info and info["entries"]:
            video_url = info["entries"][0].get("webpage_url")
            if video_url:
                open_url(video_url)
                return f"Playing {query} on YouTube."

    except Exception as e:
        logger.error(f"YouTube play error: {e}")

    encoded = urllib.parse.quote_plus(query)
    open_url(f"https://www.youtube.com/results?search_query={encoded}")
    return f"Opening YouTube search for {query}."


def play_spotify(query: str) -> str:
    query = query.strip()

    if not query:
        open_url("https://open.spotify.com")
        return "Opening Spotify."

    encoded = urllib.parse.quote_plus(query)
    url = f"https://open.spotify.com/search/{encoded}"

    open_url(url)
    return f"Opening Spotify for {query}."


def handle_media_command(user_text: str):
    text = user_text.lower().strip()

    if "youtube" in text:
        query = text
        for word in ["play", "open", "start", "search", "song", "music", "video", "on youtube", "youtube", "please"]:
            query = query.replace(word, "")
        return play_youtube(query.strip())

    if "spotify" in text:
        query = text
        for word in ["play", "open", "start", "search", "song", "music", "on spotify", "spotify", "please"]:
            query = query.replace(word, "")
        return play_spotify(query.strip())

    return None

class MediaCommandProcessor(FrameProcessor):
    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame):
            local_reply = handle_media_command(frame.text)

            if local_reply:
                logger.info(f"MEDIA COMMAND: {frame.text} -> {local_reply}")

                await self.push_frame(
                    TTSTextFrame(
                        text=local_reply,
                        aggregated_by="media_command",
                    ),
                    direction,
                )
                return

        await self.push_frame(frame, direction)