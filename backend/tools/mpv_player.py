import os
import json
import random
import re
import signal
import socket
import subprocess
import tempfile
import threading
import time
from difflib import SequenceMatcher
from loguru import logger


class MPVPlayer:
    DEFAULT_MUSIC_QUERY = "english language pop hits playlist usa uk songs -korean -kpop"
    YTMUSIC_PLAYLIST_SEARCHES = [
        "english pop hits playlist",
        "english songs playlist",
        "top english songs playlist",
        "us uk pop hits playlist",
        "english party songs playlist",
        "english radio hits playlist",
        "english workout songs playlist",
        "english chill songs playlist",
    ]
    EXCLUDED_PLAYLIST_MARKERS = {
        "kpop",
        "k-pop",
        "korean",
        "hindi",
        "bollywood",
        "tamil",
        "telugu",
        "punjabi",
        "bhojpuri",
        "marathi",
        "malayalam",
        "anime",
        "jpop",
        "j-pop",
        "lofi",
        "lo-fi",
        "sleep",
        "study",
        "focus",
        "instrumental",
        "classical",
        "jazz",
    }
    PREFERRED_PLAYLIST_MARKERS = {
        "english",
        "pop",
        "hits",
        "songs",
        "radio",
        "party",
        "workout",
        "charts",
        "top",
        "biggest",
    }
    MATCH_STOP_WORDS = {
        "a",
        "an",
        "and",
        "by",
        "feat",
        "featuring",
        "ft",
        "hd",
        "in",
        "lyrics",
        "lyric",
        "music",
        "official",
        "on",
        "remaster",
        "remastered",
        "song",
        "the",
        "track",
        "video",
        "with",
    }

    def __init__(self):
        self.process = None
        self.ipc_socket_path = os.path.join(tempfile.gettempdir(), "kairoai-mpv.sock")
        self.normal_volume = 90
        self.ducked_volume = 18
        self._is_ducked = False
        self.last_query = None
        self.history = []
        self.history_index = -1
        self.queue = []
        self.queue_index = -1
        self.queue_name = None
        self.ytmusic = None
        self._ducked_until = 0.0
        self._duck_restore_timer = None
        self._paused = False

    def stop_existing(self):
        if self.process and self.process.poll() is None:
            logger.info("Stopping existing mpv playback")
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                self.process.wait(timeout=2)
            except Exception:
                try:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                except Exception:
                    pass

        self.process = None
        self._is_ducked = False
        self._paused = False
        self._cancel_duck_restore_timer()
        try:
            os.unlink(self.ipc_socket_path)
        except FileNotFoundError:
            pass
        except Exception:
            pass

    def is_playing(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def is_paused(self) -> bool:
        if not self.is_playing():
            self._paused = False
            return False

        response = self._send_command(["get_property", "pause"])
        if response is not None and "data" in response:
            self._paused = bool(response["data"])

        return self._paused

    def is_audible(self) -> bool:
        return self.is_playing() and not self.is_paused()

    def is_ducked(self) -> bool:
        return self._is_ducked

    def _cancel_duck_restore_timer(self):
        if self._duck_restore_timer:
            self._duck_restore_timer.cancel()
            self._duck_restore_timer = None

    def _schedule_duck_restore(self, duration_sec: float):
        self._ducked_until = max(self._ducked_until, time.time() + duration_sec)
        self._cancel_duck_restore_timer()
        delay = max(0.1, self._ducked_until - time.time())
        self._duck_restore_timer = threading.Timer(delay, self._restore_volume_if_duck_expired)
        self._duck_restore_timer.daemon = True
        self._duck_restore_timer.start()

    def _restore_volume_if_duck_expired(self):
        if not self._is_ducked:
            return

        if time.time() < self._ducked_until:
            self._schedule_duck_restore(self._ducked_until - time.time())
            return

        self.restore_volume()

    def _send_command(self, command: list) -> dict | None:
        if not self.is_playing() or not os.path.exists(self.ipc_socket_path):
            return None

        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(0.5)
                client.connect(self.ipc_socket_path)
                payload = json.dumps({"command": command}).encode("utf-8") + b"\n"
                client.sendall(payload)
                data = client.recv(4096)
                if not data:
                    return None
                return json.loads(data.decode("utf-8"))
        except Exception as e:
            logger.debug(f"mpv IPC command failed {command}: {e}")
            return None

    def _wait_for_ipc(self, timeout: float = 2.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if os.path.exists(self.ipc_socket_path):
                return
            time.sleep(0.05)

    def get_audio_url_from_source(
        self,
        source: str,
        *,
        log_label: str | None = None,
        random_choice: bool = False,
    ) -> str | None:
        source = source.strip()

        if not source:
            return None

        logger.info(f"Getting YouTube audio URL for: {log_label or source}")

        try:
            result = subprocess.run(
                [
                    "/home/tanzo/Kyron_automation/KairoAI-Assistant/backend/.venv/bin/yt-dlp",
                    "-f",
                    "bestaudio",
                    "-g",
                    source,
                ],
                capture_output=True,
                text=True,
                timeout=20,
            )

            if result.returncode != 0:
                logger.error(f"yt-dlp error: {result.stderr.strip()}")
                return None

            urls = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            if not urls:
                return None

            url = random.choice(urls) if random_choice else urls[0]
            return url

        except Exception as e:
            logger.error(f"Failed to get audio URL: {e}")
            return None

    def get_audio_url(self, query: str, *, random_choice: bool = False) -> str | None:
        query = query.strip()

        if not query:
            return None

        search_count = 10 if random_choice else 1
        return self.get_audio_url_from_source(
            f"ytsearch{search_count}:{query}",
            log_label=query,
            random_choice=random_choice,
        )

    def get_youtube_music(self):
        if self.ytmusic is None:
            from ytmusicapi import YTMusic

            self.ytmusic = YTMusic(language="en", location="US")

        return self.ytmusic

    def is_english_playlist_candidate(self, playlist: dict) -> bool:
        text = " ".join(
            str(value)
            for value in [
                playlist.get("title", ""),
                playlist.get("author", ""),
                playlist.get("description", ""),
            ]
        ).lower()

        if any(marker in text for marker in self.EXCLUDED_PLAYLIST_MARKERS):
            return False

        title = str(playlist.get("title", "")).lower()
        return any(marker in title for marker in self.PREFERRED_PLAYLIST_MARKERS)

    def track_display_name(self, track: dict) -> str:
        title = track.get("title") or "song"
        artists = track.get("artists") or []
        artist_names = [
            artist.get("name")
            for artist in artists
            if isinstance(artist, dict) and artist.get("name")
        ]

        if artist_names:
            return f"{title} by {', '.join(artist_names[:2])}"

        return title

    def track_search_query(self, track: dict) -> str:
        return self.track_display_name(track)

    def track_source(self, track: dict) -> str:
        video_id = track.get("videoId")

        if video_id:
            return f"https://music.youtube.com/watch?v={video_id}"

        return f"ytsearch1:{self.track_search_query(track)}"

    def clean_match_text(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r"\([^)]*\)|\[[^]]*\]", " ", text)
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def match_tokens(self, text: str) -> set[str]:
        return {
            token
            for token in self.clean_match_text(text).split()
            if token not in self.MATCH_STOP_WORDS and len(token) > 1
        }

    def track_match_score(self, query: str, track: dict) -> tuple[float, float]:
        query_text = self.clean_match_text(query)
        track_text = self.clean_match_text(self.track_display_name(track))

        if not query_text or not track_text:
            return 0.0, 0.0

        ratio = SequenceMatcher(None, query_text, track_text).ratio()
        query_tokens = self.match_tokens(query)
        track_tokens = self.match_tokens(self.track_display_name(track))

        if not query_tokens or not track_tokens:
            return ratio, 0.0

        overlap = len(query_tokens.intersection(track_tokens)) / len(query_tokens)
        score = max(ratio, (overlap * 0.85) + (ratio * 0.15))
        return score, overlap

    def find_best_song_match(self, query: str) -> dict | None:
        try:
            ytmusic = self.get_youtube_music()
            candidates = []

            for filter_name in ("songs", "videos"):
                try:
                    candidates.extend(ytmusic.search(query, filter=filter_name, limit=5))
                except Exception as e:
                    logger.debug(f"YouTube Music {filter_name} search failed for '{query}': {e}")

            playable = [
                track
                for track in candidates
                if track.get("videoId") and track.get("isAvailable", True)
            ]

            if not playable:
                return None

            ranked = [
                (*self.track_match_score(query, track), track)
                for track in playable
            ]
            ranked.sort(key=lambda item: item[0], reverse=True)

            score, overlap, track = ranked[0]
            logger.info(
                f"Best YouTube Music match for '{query}': "
                f"'{self.track_display_name(track)}' score={score:.2f} overlap={overlap:.2f}"
            )

            if score >= 0.58 and overlap >= 0.5:
                return track

            return None

        except Exception as e:
            logger.error(f"Failed to validate song search with YouTube Music: {e}")
            return None

    def not_found_response(self, query: str) -> str:
        return f"I couldn't find {query}."

    def load_youtube_music_queue(self) -> bool:
        try:
            ytmusic = self.get_youtube_music()
            candidates = []
            search_queries = random.sample(
                self.YTMUSIC_PLAYLIST_SEARCHES,
                k=len(self.YTMUSIC_PLAYLIST_SEARCHES),
            )

            for search_query in search_queries:
                logger.info(f"Searching YouTube Music playlists for: {search_query}")
                playlists = ytmusic.search(search_query, filter="featured_playlists", limit=20)
                candidates = [
                    playlist
                    for playlist in playlists
                    if playlist.get("browseId") and self.is_english_playlist_candidate(playlist)
                ]

                if candidates:
                    break

            if not candidates:
                return False

            playlist = random.choice(candidates)
            playlist_id = playlist["browseId"]
            playlist_data = ytmusic.get_playlist(playlist_id, limit=100)
            tracks = [
                track
                for track in playlist_data.get("tracks", [])
                if track.get("videoId") and track.get("isAvailable", True)
            ]

            if not tracks:
                return False

            random.shuffle(tracks)
            self.queue = tracks
            self.queue_index = -1
            self.queue_name = playlist_data.get("title") or playlist.get("title") or "English playlist"
            logger.info(f"Loaded YouTube Music playlist queue: {self.queue_name} ({len(self.queue)} tracks)")
            return True

        except Exception as e:
            logger.error(f"Failed to load YouTube Music playlist: {e}")
            self.queue = []
            self.queue_index = -1
            self.queue_name = None
            return False

    def load_related_queue(self, seed_track: dict, audio_url: str | None = None) -> bool:
        video_id = seed_track.get("videoId")

        if not video_id:
            return False

        display_name = self.track_display_name(seed_track)
        seed_track = dict(seed_track)

        if audio_url:
            seed_track["audio_url"] = audio_url

        try:
            ytmusic = self.get_youtube_music()
            watch_playlist = ytmusic.get_watch_playlist(
                videoId=video_id,
                limit=25,
                radio=True,
            )
            related_tracks = watch_playlist.get("tracks", [])
        except Exception as e:
            logger.error(f"Failed to load related queue for '{display_name}': {e}")
            return False

        queue = [seed_track]
        seen_video_ids = {video_id}

        for track in related_tracks:
            track_video_id = track.get("videoId")

            if (
                not track_video_id
                or track_video_id in seen_video_ids
                or not track.get("isAvailable", True)
            ):
                continue

            queue.append(track)
            seen_video_ids.add(track_video_id)

        if len(queue) <= 1:
            logger.warning(f"Related queue for '{display_name}' had no follow-up tracks")
            return False

        self.queue = queue
        self.queue_index = 0
        self.queue_name = f"Radio from {display_name}"
        logger.info(f"Loaded related queue: {self.queue_name} ({len(self.queue)} tracks)")
        return True

    def play_queue_track(self, index: int, *, remember: bool = True) -> str:
        if not self.queue:
            return "I could not find a playlist."

        if index < 0 or index >= len(self.queue):
            return "No more songs in this playlist."

        track = self.queue[index]
        display_name = self.track_display_name(track)
        source = self.track_source(track)
        audio_url = track.get("audio_url") or self.get_audio_url_from_source(source, log_label=display_name)

        if not audio_url:
            audio_url = self.get_audio_url(self.track_search_query(track))

        if not audio_url:
            return "I could not play that song."

        track["audio_url"] = audio_url
        self.queue_index = index
        self._start_url(display_name, audio_url)

        if remember:
            self._remember_track(display_name, audio_url)

        return f"Playing {display_name}"

    def play_default_music(self):
        if self.load_youtube_music_queue():
            return self.play_queue_track(0)

        logger.warning("Falling back to yt-dlp search for default music")
        return self.play_search(self.DEFAULT_MUSIC_QUERY, random_choice=True)

    def _remember_track(self, query: str, audio_url: str):
        if self.history_index < len(self.history) - 1:
            self.history = self.history[: self.history_index + 1]

        if self.history and self.history[-1]["audio_url"] == audio_url:
            self.history_index = len(self.history) - 1
            return

        self.history.append({"query": query, "audio_url": audio_url})

        if len(self.history) > 50:
            self.history = self.history[-50:]

        self.history_index = len(self.history) - 1

    def _start_url(self, query: str, audio_url: str):
        self.stop_existing()
        self.last_query = query
        logger.info(f"Playing with mpv: {query}")

        self.process = subprocess.Popen(
            [
                "mpv",
                "--no-video",
                "--no-terminal",
                "--force-window=no",
                f"--input-ipc-server={self.ipc_socket_path}",
                f"--volume={self.normal_volume}",
                audio_url,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self._paused = False
        self._wait_for_ipc()

    def _run_playerctl(self, *args: str) -> bool:
        try:
            result = subprocess.run(
                ["playerctl", *args],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def play_search(self, query: str, *, random_choice: bool = False):
        self.queue = []
        self.queue_index = -1
        self.queue_name = None
        self.last_query = query

        if random_choice:
            audio_url = self.get_audio_url(query, random_choice=True)

            if not audio_url:
                return self.not_found_response(query)
        else:
            track = self.find_best_song_match(query)

            if not track:
                return self.not_found_response(query)

            display_name = self.track_display_name(track)
            audio_url = self.get_audio_url_from_source(
                self.track_source(track),
                log_label=display_name,
            )

            if not audio_url:
                return self.not_found_response(query)

            query = display_name
            self.load_related_queue(track, audio_url)

        self._start_url(query, audio_url)
        self._remember_track(query, audio_url)

        return f"Playing {query}"

    def pause(self):
        if self._send_command(["set_property", "pause", True]) is None:
            if not self._run_playerctl("pause"):
                return "Nothing is playing."
        self._paused = True
        return "Paused"

    def play(self):
        if self._send_command(["set_property", "pause", False]) is None:
            if self.last_query:
                return self.play_search(self.last_query)

            if self._run_playerctl("play"):
                self._paused = False
                return "Playing"

            return self.play_default_music()
        self._paused = False
        return "Playing"

    def play_pause(self):
        if self._send_command(["cycle", "pause"]) is None:
            self._run_playerctl("play-pause")
            self._paused = not self._paused
        else:
            self._paused = not self._paused
        return "Toggled playback"

    def stop(self):
        self.stop_existing()
        return "Stopped"

    def next(self):
        if self.queue:
            next_index = self.queue_index + 1

            if next_index >= len(self.queue):
                random.shuffle(self.queue)
                next_index = 0

            return self.play_queue_track(next_index)

        query = self.last_query or self.DEFAULT_MUSIC_QUERY
        return self.play_search(query, random_choice=True)

    def previous(self):
        if self.queue and self.queue_index > 0:
            return self.play_queue_track(self.queue_index - 1, remember=False)

        if self.history_index > 0:
            self.history_index -= 1
            track = self.history[self.history_index]
            self._start_url(track["query"], track["audio_url"])
            return "Playing previous song"

        if self._send_command(["playlist-prev"]) is not None:
            return "Playing previous song"

        if self._run_playerctl("previous"):
            return "Playing previous song"

        return "No previous song."

    def duck(self, duration_sec: float = 8.0):
        if not self.is_audible():
            return

        if self._is_ducked:
            self._schedule_duck_restore(duration_sec)
            return

        logger.debug("Ducking mpv volume for user speech")
        if self._send_command(["set_property", "volume", self.ducked_volume]) is not None:
            self._is_ducked = True
            self._schedule_duck_restore(duration_sec)

    def restore_volume(self):
        if not self.is_playing():
            self._is_ducked = False
            self._ducked_until = 0.0
            self._cancel_duck_restore_timer()
            return

        if not self._is_ducked:
            return

        logger.debug("Restoring mpv volume after user speech")
        self._send_command(["set_property", "volume", self.normal_volume])
        self._is_ducked = False
        self._ducked_until = 0.0
        self._cancel_duck_restore_timer()

    def volume_up(self):
        self.restore_volume()
        self.normal_volume = min(100, self.normal_volume + 10)
        if self._send_command(["add", "volume", 10]) is None:
            self._run_playerctl("volume", "0.1+")
        return "Volume increased"

    def volume_down(self):
        self.normal_volume = max(0, self.normal_volume - 10)
        if self._send_command(["add", "volume", -10]) is None:
            self._run_playerctl("volume", "0.1-")
        return "Volume decreased"

    def mute(self):
        if self._send_command(["set_property", "mute", True]) is None:
            self._run_playerctl("volume", "0")
        return "Muted"

    def unmute(self):
        if self._send_command(["set_property", "mute", False]) is None:
            self._run_playerctl("volume", "0.7")
        return "Unmuted"
