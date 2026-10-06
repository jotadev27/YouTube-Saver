import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from youtube_saver.downloads import DownloadEngine, MediaType, build_command, sanitize_log, youtube_url
from youtube_saver.paths import AppPaths, folder_label
from youtube_saver.settings import Settings


class LinksAndFormats(unittest.TestCase):
    def test_links_strip_playlists_and_tracking(self):
        for link in ("youtu.be/YE7VzlLtp-4?t=2", "https://music.youtube.com/watch?v=YE7VzlLtp-4&list=test",
                     "https://www.youtube.com/shorts/YE7VzlLtp-4", "https://m.youtube.com/live/YE7VzlLtp-4"):
            self.assertEqual(youtube_url(link), "https://www.youtube.com/watch?v=YE7VzlLtp-4")

    def test_untrusted_sites_and_command_input_are_rejected(self):
        for link in ("https://youtube.com.evil.invalid/watch?v=YE7VzlLtp-4", "file:///test",
                     "https://youtube.com@evil.invalid/watch?v=YE7VzlLtp-4", "https://youtube.com/playlist?list=test",
                     "https://youtube.com:443/watch?v=YE7VzlLtp-4", "--exec calc", "https://youtu.be/bad"):
            with self.assertRaises(ValueError, msg=link):
                youtube_url(link)

    def test_video_has_no_resolution_or_codec_restriction(self):
        command = build_command("youtu.be/YE7VzlLtp-4", MediaType.VIDEO, Path("output"), Path("tools"))
        selector = command[command.index("-f") + 1]
        self.assertEqual(selector, "bv*+ba/b")
        self.assertNotIn("1080", " ".join(command))
        self.assertNotIn("--recode-video", command)

    def test_security_flags_and_argument_boundaries(self):
        destination = Path("Folder with spaces & symbols")
        command = build_command("youtu.be/YE7VzlLtp-4", MediaType.AUDIO, destination, Path("tools"))
        self.assertEqual(command[command.index("-P") + 1], str(destination))
        for flag in ("--ignore-config", "--no-plugin-dirs", "--no-remote-components", "--no-update", "--no-playlist"):
            self.assertIn(flag, command)
        self.assertEqual(command[-2], "--")
        self.assertEqual(command[command.index("--audio-format") + 1], "mp3")


class LocalSettings(unittest.TestCase):
    def test_settings_and_invalid_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = Settings(root / "settings", root / "Downloads")
            self.assertEqual(settings.load_folder(), root / "Downloads")
            settings.save_folder(root / "Custom")
            self.assertEqual(settings.load_folder(), root / "Custom")
            settings.file.write_text('{"folder":"relative"}', encoding="utf-8")
            self.assertEqual(settings.load_folder(), root / "Downloads")
            settings.file.write_text("invalid", encoding="utf-8")
            self.assertEqual(settings.load_folder(), root / "Downloads")

    def test_display_and_logs_do_not_show_home_path(self):
        home = Path.home()
        downloads = home / "Downloads"
        self.assertEqual(folder_label(downloads, downloads), "Save to: Downloads")
        self.assertNotIn(str(home), folder_label(home / "Neutral folder", downloads))
        paths = AppPaths(home / "App", home / "App" / "tools", home / "Settings", downloads)
        self.assertNotIn(str(home), sanitize_log(f"Error in {home / 'App'} and {downloads}", paths))


class DownloadLifecycle(unittest.TestCase):
    def run_worker(self, text, code, cancelled=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = AppPaths(root, root / "tools", root / "settings", root / "Downloads")
            engine = DownloadEngine(paths)
            if cancelled:
                engine._cancel.set()
            process = MagicMock()
            process.__enter__.return_value = process
            process.stdout = io.StringIO(text)
            process.wait.return_value = code
            process.poll.return_value = code
            with patch("youtube_saver.downloads.subprocess.Popen", return_value=process) as popen:
                engine._download(["tool", "url"])
            self.assertNotIn("shell", popen.call_args.kwargs)
            self.assertIsNone(engine._process)
            events = []
            while not engine.events.empty():
                events.append(engine.events.get_nowait())
            return events

    def test_success_requires_a_real_final_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "test.mp4"
            output.write_bytes(b"test")
            events = self.run_worker(f"PROGRESS:50.0%|1MiB/s|00:01\nFILE:{output}\n", 0)
            self.assertEqual(events[0].kind, "progress")
            self.assertEqual(events[-1].kind, "success")
        self.assertEqual(self.run_worker("FILE:missing.mp4\n", 0)[-1].kind, "done")

    def test_restricted_video_and_cancellation(self):
        self.assertEqual(self.run_worker("ERROR: private video\n", 1)[-1].kind, "error")
        self.assertEqual(self.run_worker("", 1, cancelled=True)[-1].kind, "cancelled")

    def test_cancel_terminates_the_process_tree(self):
        paths = AppPaths(Path("app"), Path("tools"), Path("settings"), Path("Downloads"))
        engine = DownloadEngine(paths)
        process = MagicMock()
        process.pid = 12345
        process.poll.return_value = None
        engine._process = process
        with patch("youtube_saver.downloads.subprocess.run") as run, patch("youtube_saver.downloads.os.name", "nt"):
            run.return_value.returncode = 0
            engine._stop_process()
            self.assertEqual(run.call_args.args[0][-4:], ["/PID", "12345", "/T", "/F"])


if __name__ == "__main__":
    unittest.main()
