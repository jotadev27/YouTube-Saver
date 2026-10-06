"""Resolve resources and Windows known folders without hardcoded user paths."""
import ctypes
import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

from . import APP_NAME

DOWNLOADS_ID = "374DE290-123F-4565-9164-39C4925E467B"
LOCAL_APP_DATA_ID = "F1B32785-6FBA-4FCF-9D55-7B8E7F157091"


def known_folder(identifier: str, fallback: Path) -> Path:
    if os.name != "nt":
        return fallback
    guid = (ctypes.c_ubyte * 16).from_buffer_copy(uuid.UUID(identifier).bytes_le)
    pointer = ctypes.c_void_p()
    shell = ctypes.WinDLL("shell32")
    shell.SHGetKnownFolderPath.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    shell.SHGetKnownFolderPath.restype = ctypes.c_long
    result = shell.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(pointer))
    if result != 0 or not pointer.value:
        return fallback
    try:
        return Path(ctypes.wstring_at(pointer.value))
    finally:
        free = ctypes.WinDLL("ole32").CoTaskMemFree
        free.argtypes = [ctypes.c_void_p]
        free(pointer)


@dataclass(frozen=True)
class AppPaths:
    resources: Path
    tools: Path
    user_data: Path
    downloads: Path

    @classmethod
    def discover(cls):
        project = Path(__file__).resolve().parents[2]
        resources = Path(getattr(sys, "_MEIPASS", project))
        frozen = bool(getattr(sys, "frozen", False))
        executable_folder = Path(sys.executable).resolve().parent
        portable = frozen and ("-Portable" in Path(sys.executable).stem or (executable_folder / "portable.flag").is_file())
        data = executable_folder / "settings" if portable else known_folder(LOCAL_APP_DATA_ID, Path.home() / ".local" / "share") / APP_NAME
        tools = resources / "tools" if frozen else project / ".build" / "tools"
        return cls(resources, tools, data, known_folder(DOWNLOADS_ID, Path.home() / "Downloads"))


def folder_label(destination: Path, downloads: Path) -> str:
    if destination == downloads:
        return "Save to: Downloads"
    if destination == Path.home():
        return "Save to: Home folder"
    name = destination.name or destination.anchor
    return "Save to: " + (name if len(name) < 35 else name[:32] + "…")
