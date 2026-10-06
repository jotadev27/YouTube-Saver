"""Validate links, construct safe commands, and manage one download process."""
import os
import queue
import re
import subprocess
import threading
from collections import deque
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .paths import AppPaths

HIDDEN = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
TOOL_NAMES = ("yt-dlp.exe", "deno.exe", "ffmpeg.exe", "ffprobe.exe")


class MediaType(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"


@dataclass(frozen=True)
class DownloadEvent:
    kind: str
    text: str


def youtube_url(value: str) -> str:
    """Return a single canonical YouTube video URL, with tracking removed."""
    value = value.strip()
    if not value.startswith(("https://", "http://")):
        value = "https://" + value
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"https", "http"} or parsed.username or parsed.password or parsed.port:
            raise ValueError()
        host = (parsed.hostname or "").lower()
        parts = parsed.path.strip("/").split("/")
        if host in {"youtu.be", "www.youtu.be"} and len(parts) == 1:
            video_id = parts[0]
        elif host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
            if parsed.path == "/watch":
                video_id = parse_qs(parsed.query).get("v", [""])[0]
            elif len(parts) == 2 and parts[0] in {"shorts", "live", "embed"}:
                video_id = parts[1]
            else:
                raise ValueError()
        else:
            raise ValueError()
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            raise ValueError()
    except (ValueError, IndexError):
        raise ValueError("Paste a YouTube video link, not a playlist or channel.") from None
    return "https://www.youtube.com/watch?v=" + video_id


def build_command(url: str, media: MediaType, destination: Path, tools: Path) -> list[str]:
    media = MediaType(media)
    command = [
        str(tools / "yt-dlp.exe"), "--ignore-config", "--no-plugin-dirs",
        "--no-playlist", "--no-update", "--no-cache-dir", "--no-colors",
        "--newline", "--progress", "--no-overwrites", "--no-mtime",
        "--windows-filenames", "--trim-filenames", "140", "--encoding", "utf-8",
        "--socket-timeout", "20", "--retries", "3", "--fragment-retries", "3",
        "--no-js-runtimes", "--js-runtimes", f"deno:{tools / 'deno.exe'}",
        "--no-remote-components", "--ffmpeg-location", str(tools),
        "--progress-template", "download:PROGRESS:%(progress._percent_str)s|%(progress._speed_str)s|%(progress._eta_str)s",
        "--print", "after_move:FILE:%(filepath)s",
        "-P", str(destination), "-o", "%(title)s [%(id)s].%(ext)s",
    ]
    if media == MediaType.AUDIO:
        command += ["-f", "bestaudio/best", "-x", "--audio-format", "mp3", "--audio-quality", "0"]
    else:
        # Select the best available streams, regardless of resolution or codec.
        # Remuxing preserves the original streams instead of reducing their quality.
        command += ["-f", "bv*+ba/b", "--merge-output-format", "mp4", "--remux-video", "mp4"]
    return command + ["--", youtube_url(url)]


def sanitize_log(text: str, paths: AppPaths) -> str:
    for location, replacement in ((paths.resources, "[app]"), (paths.user_data, "[settings]"), (Path.home(), "[user]")):
        for spelling in {str(location), location.as_posix()}:
            text = text.replace(spelling, replacement)
    return text


class DownloadEngine:
    def __init__(self, paths: AppPaths):
        self.paths = paths
        self.events: queue.Queue[DownloadEvent] = queue.Queue()
        self._cancel = threading.Event()
        self._lock = threading.Lock()
        self._process = None
        self._thread = None

    def start(self, url: str, media: MediaType, destination: Path) -> None:
        if self._thread is not None and self._thread.is_alive():
            raise ValueError("A download is already running.")
        command = build_command(url, media, destination, self.paths.tools)
        if any(not (self.paths.tools / name).is_file() for name in TOOL_NAMES):
            raise ValueError("Required tools are missing. Reinstall YouTube Saver.")
        destination.mkdir(parents=True, exist_ok=True)
        self._cancel.clear()
        self._thread = threading.Thread(target=self._download, args=(command,), daemon=True)
        self._thread.start()

    def _send(self, kind: str, text: str) -> None:
        self.events.put(DownloadEvent(kind, text))

    def _download(self, command: list[str]) -> None:
        logs = deque(maxlen=60)
        output_file = ""
        final = DownloadEvent("error", "Download failed. Check the link and your connection.")
        try:
            with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
                                  creationflags=HIDDEN, cwd=self.paths.tools) as process:
                with self._lock:
                    self._process = process
                if self._cancel.is_set():
                    self._stop_process()
                for line in process.stdout:
                    line = line.strip()
                    logs.append(line)
                    if line.startswith("PROGRESS:"):
                        self._send("progress", line[9:])
                    elif line.startswith("FILE:"):
                        output_file = line[5:]
                    elif line.startswith(("[ExtractAudio]", "[Merger]", "[VideoRemuxer]")):
                        self._send("status", "Preparing the final file…")
                code = process.wait()
            if self._cancel.is_set():
                final = DownloadEvent("cancelled", "Download cancelled. You can try again.")
            elif code == 0 and output_file and Path(output_file).is_file():
                final = DownloadEvent("success", "Done. Your file is ready.")
            elif code == 0:
                final = DownloadEvent("done", "The file may already exist. Check the selected folder.")
            else:
                details = "\n".join(logs)
                self._save_error(details)
                message = "Download failed. Check the link and your connection."
                if any(word in details.lower() for word in ("sign in", "private video", "age-restricted", "not available", "unavailable")):
                    message = "YouTube restricts this video. Try another public video."
                final = DownloadEvent("error", message)
        except OSError as error:
            self._save_error(str(error))
            final = DownloadEvent("error", "Unable to start the download. Check the app files and folder permissions.")
        finally:
            with self._lock:
                self._process = None
            self.events.put(final)

    def _save_error(self, details: str) -> None:
        try:
            self.paths.user_data.mkdir(parents=True, exist_ok=True)
            (self.paths.user_data / "last-error.log").write_text(sanitize_log(details, self.paths), encoding="utf-8")
        except OSError:
            pass

    def cancel(self) -> None:
        self._cancel.set()
        threading.Thread(target=self._stop_process, daemon=True).start()

    def _stop_process(self) -> None:
        with self._lock:
            process = self._process
        if process is None or process.poll() is not None:
            return
        try:
            if os.name == "nt":
                system = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32" / "taskkill.exe"
                result = subprocess.run([str(system), "/PID", str(process.pid), "/T", "/F"],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                        creationflags=HIDDEN, timeout=10)
                if result.returncode and process.poll() is None:
                    process.kill()
            else:
                process.terminate()
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
            except OSError:
                pass
