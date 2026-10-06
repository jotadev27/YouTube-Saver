"""Keep the title icon small while giving the taskbar a full-size icon."""
import ctypes
import os
from pathlib import Path


def set_taskbar_icon(root, resources: Path):
    if os.name != "nt":
        return
    icon_file = resources / "assets" / "desktop.ico"
    if not icon_file.is_file():
        return
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    user32.GetAncestor.restype = ctypes.c_void_p
    user32.LoadImageW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32,
                                ctypes.c_int, ctypes.c_int, ctypes.c_uint32]
    user32.LoadImageW.restype = ctypes.c_void_p
    user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_size_t, ctypes.c_void_p]
    user32.SendMessageW.restype = ctypes.c_ssize_t
    user32.DestroyIcon.argtypes = [ctypes.c_void_p]
    root.update_idletasks()
    window = user32.GetAncestor(root.winfo_id(), 2)
    icon = user32.LoadImageW(None, str(icon_file), 1, 48, 48, 0x10)
    if window and icon:
        user32.SendMessageW(window, 0x80, 1, icon)  # WM_SETICON / ICON_BIG only.

        def release(event):
            if event.widget is root:
                user32.DestroyIcon(icon)

        root.bind("<Destroy>", release, add=True)
    elif icon:
        user32.DestroyIcon(icon)
