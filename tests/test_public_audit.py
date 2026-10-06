import io
import sys
import unittest
from pathlib import Path

from PIL import Image
from PIL.PngImagePlugin import PngInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_release import audit_content


class PublicRepositoryAudit(unittest.TestCase):
    def test_downloads_and_installers_are_rejected(self):
        for name in ("video.mp4", "music.mp3", "setup.exe", "library.dll", "archive.zip"):
            with self.assertRaises(RuntimeError):
                audit_content(name, b"local file")

    def test_home_paths_and_token_shaped_values_are_rejected(self):
        for content in (str(Path.home() / "private" / "settings.json"), "ghp_" + "A" * 36):
            with self.assertRaises(RuntimeError):
                audit_content("example.py", content.encode("utf-8"))
        audit_content("example.py", b"print('public source')")

    def test_only_reviewed_image_paths_are_allowed(self):
        with self.assertRaises(RuntimeError):
            audit_content("personal-photo.png", b"image")
        image = Image.new("RGB", (16, 16), "white")
        output = io.BytesIO()
        image.save(output, format="PNG")
        audit_content("assets/logo.png", output.getvalue())

    def test_image_text_metadata_is_rejected(self):
        image = Image.new("RGB", (16, 16), "white")
        metadata = PngInfo()
        metadata.add_text("Author", "local metadata")
        output = io.BytesIO()
        image.save(output, format="PNG", pnginfo=metadata)
        with self.assertRaises(RuntimeError):
            audit_content("assets/logo.png", output.getvalue())


if __name__ == "__main__":
    unittest.main()
