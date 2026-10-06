"""The minimal English-language Windows interface."""
import ctypes
import os
import queue
import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import APP_NAME
from .branding import set_taskbar_icon
from .downloads import DownloadEngine, MediaType
from .paths import AppPaths, folder_label
from .settings import Settings


class SaverWindow:
    def __init__(self, root: tk.Tk, paths: AppPaths):
        self.root = root
        self.paths = paths
        self.settings = Settings(paths.user_data, paths.downloads)
        self.engine = DownloadEngine(paths)
        self.destination = self.settings.load_folder()
        self.busy = False
        self.closing = False

        root.title(APP_NAME)
        root.geometry("600x370")
        root.resizable(False, False)
        icon = paths.resources / "assets" / "icon.ico"
        if icon.is_file():
            root.iconbitmap(default=str(icon))
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=(10, 5))
        frame = ttk.Frame(root, padding=22)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text=APP_NAME, font=("Segoe UI", 17, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(frame, text="Save videos and music from YouTube").grid(row=1, column=0, sticky="w", pady=(2, 16))

        entry_row = ttk.Frame(frame)
        entry_row.grid(row=2, column=0, sticky="ew")
        entry_row.columnconfigure(0, weight=1)
        self.url = tk.StringVar()
        self.entry = ttk.Entry(entry_row, textvariable=self.url, font=("Segoe UI", 10))
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.paste_button = ttk.Button(entry_row, text="Paste link", command=self.paste)
        self.paste_button.grid(row=0, column=1)
        self.entry.bind("<Return>", lambda event: self.start())

        self.mode = tk.StringVar(value=MediaType.VIDEO.value)
        modes = ttk.Frame(frame)
        modes.grid(row=3, column=0, sticky="w", pady=12)
        self.video_button = ttk.Radiobutton(modes, text="Video MP4", variable=self.mode, value=MediaType.VIDEO.value)
        self.video_button.pack(side="left", padx=(0, 20))
        self.audio_button = ttk.Radiobutton(modes, text="Music MP3", variable=self.mode, value=MediaType.AUDIO.value)
        self.audio_button.pack(side="left")

        folder_row = ttk.Frame(frame)
        folder_row.grid(row=4, column=0, sticky="ew")
        folder_row.columnconfigure(0, weight=1)
        self.folder_label = ttk.Label(folder_row, text=folder_label(self.destination, paths.downloads))
        self.folder_label.grid(row=0, column=0, sticky="w")
        self.change_button = ttk.Button(folder_row, text="Change folder", command=self.choose_folder)
        self.change_button.grid(row=0, column=1)

        self.progress = ttk.Progressbar(frame, maximum=100)
        self.progress.grid(row=5, column=0, sticky="ew", pady=(15, 6))
        self.status = tk.StringVar(value="Paste a link to get started.")
        self.status_label = ttk.Label(frame, textvariable=self.status, wraplength=550)
        self.status_label.grid(row=6, column=0, sticky="w")
        frame.bind("<Configure>", lambda event: self.status_label.configure(wraplength=max(200, event.width - 44)))
        actions = ttk.Frame(frame)
        actions.grid(row=7, column=0, sticky="ew", pady=(12, 0))
        self.download_button = ttk.Button(actions, text="Download", command=self.start)
        self.download_button.pack(side="left")
        self.cancel_button = ttk.Button(actions, text="Cancel", command=self.cancel, state="disabled")
        self.cancel_button.pack(side="left", padx=8)
        ttk.Button(actions, text="Open folder", command=self.open_folder).pack(side="right")
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.entry.focus_set()
        set_taskbar_icon(root, paths.resources)
        root.after(100, self.poll)

    def paste(self):
        try:
            self.url.set(self.root.clipboard_get().strip())
        except tk.TclError:
            self.status.set("The clipboard does not contain a link.")

    def choose_folder(self):
        initial = self.destination if self.destination.exists() else self.paths.downloads
        selected = filedialog.askdirectory(title="Choose download folder", initialdir=str(initial))
        if selected:
            self.destination = Path(selected)
            self.folder_label.configure(text=folder_label(self.destination, self.paths.downloads))
            try:
                self.settings.save_folder(self.destination)
            except OSError:
                self.status.set("Folder selected. The preference could not be saved.")

    def open_folder(self):
        try:
            self.destination.mkdir(parents=True, exist_ok=True)
            os.startfile(self.destination)
        except OSError:
            messagebox.showerror(APP_NAME, "Unable to open this folder. Check its permissions.")

    def set_busy(self, busy):
        self.busy = busy
        for widget in (self.entry, self.paste_button, self.video_button, self.audio_button, self.change_button, self.download_button):
            widget.configure(state="disabled" if busy else "normal")
        self.cancel_button.configure(state="normal" if busy else "disabled")

    def start(self):
        if self.busy:
            return
        try:
            self.engine.start(self.url.get(), MediaType(self.mode.get()), self.destination)
        except ValueError as error:
            messagebox.showerror(APP_NAME, str(error))
            return
        except OSError:
            messagebox.showerror(APP_NAME, "Unable to write to this folder. Choose a different one.")
            return
        self.set_busy(True)
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self.status.set("Finding your video…")

    def cancel(self):
        self.cancel_button.configure(state="disabled")
        self.status.set("Cancelling…")
        self.engine.cancel()

    def close(self):
        if self.busy:
            self.closing = True
            self.cancel()
        else:
            self.root.destroy()

    def poll(self):
        try:
            while True:
                event = self.engine.events.get_nowait()
                if event.kind == "progress":
                    percent, speed, eta = (event.text.split("|") + ["", ""])[:3]
                    match = re.search(r"([\d.]+)%", percent)
                    if match:
                        self.progress.stop()
                        self.progress.configure(mode="determinate", value=float(match[1]))
                    extras = [part.strip() for part in (speed, eta) if part.strip() not in {"", "NA", "Unknown"}]
                    self.status.set("Downloading " + percent.strip() + (" · " + " · ".join(extras) if extras else ""))
                elif event.kind == "status":
                    self.status.set(event.text)
                else:
                    self.progress.stop()
                    self.progress.configure(mode="determinate", value=100 if event.kind == "success" else 0)
                    self.set_busy(False)
                    self.status.set(event.text)
                    if self.closing:
                        self.root.destroy()
                        return
        except queue.Empty:
            pass
        self.root.after(100, self.poll)


def run():
    if os.name == "nt":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("YouTubeSaver.Desktop")
    root = tk.Tk()
    SaverWindow(root, AppPaths.discover())
    root.mainloop()
