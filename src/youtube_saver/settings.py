"""Store the selected folder locally; no settings are bundled in releases."""
import json
from pathlib import Path


class Settings:
    def __init__(self, directory: Path, default_folder: Path):
        self.directory = directory
        self.default_folder = default_folder
        self.file = directory / "settings.json"

    def load_folder(self) -> Path:
        try:
            data = json.loads(self.file.read_text(encoding="utf-8"))
            value = data["folder"]
            if not isinstance(value, str) or not value:
                return self.default_folder
            folder = Path(value)
            return folder if folder.is_absolute() else self.default_folder
        except (OSError, ValueError, TypeError, KeyError):
            return self.default_folder

    def save_folder(self, folder: Path) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = self.file.with_suffix(".tmp")
        temporary.write_text(json.dumps({"folder": str(folder)}, indent=2), encoding="utf-8")
        temporary.replace(self.file)
