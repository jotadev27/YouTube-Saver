"""Audit public source, the exact Git index, and local release exclusions."""
import argparse
import io
import marshal
import re
import subprocess
import types
from pathlib import Path

from PIL import Image
from PyInstaller.archive.readers import CArchiveReader

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_VISUALS = frozenset({
    "assets/logo.png", "assets/icon.ico", "assets/desktop.ico", "assets/installer-banner.png",
    "docs/screenshots/video.png", "docs/screenshots/music.png", "docs/screenshots/installer.png",
})
BINARY_EXTENSIONS = frozenset({
    ".exe", ".dll", ".pyd", ".msi", ".msix", ".zip", ".7z", ".rar", ".tar", ".gz", ".xz",
    ".mp4", ".mp3", ".m4a", ".aac", ".ogg", ".flac", ".wav", ".webm", ".mkv", ".mov", ".avi",
})
SAFE_IMAGE_METADATA = frozenset({"sizes", "dpi", "icc_profile", "gamma", "srgb", "transparency"})
SECRET_PATTERNS = (
    r"\bgh[pousr]_[A-Za-z0-9]{30,}\b",
    r"\bgithub_pat_[A-Za-z0-9_]{40,}\b",
    r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
    r"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}\b",
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
)


def audit_content(name: str, content: bytes) -> None:
    path = Path(name)
    if path.suffix.lower() in BINARY_EXTENSIONS:
        raise RuntimeError(f"A local binary or downloaded media file is public: {name}")
    if name in PUBLIC_VISUALS:
        with Image.open(io.BytesIO(content)) as image:
            if set(image.info) - SAFE_IMAGE_METADATA or image.getexif():
                raise RuntimeError(f"Unreviewed image metadata found: {name}")
            if path.suffix == ".png" and image.format != "PNG":
                raise RuntimeError(f"Image format does not match its extension: {name}")
        return
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".ico", ".gif", ".webp", ".bmp", ".tif", ".tiff"}:
        raise RuntimeError(f"Image is not in the reviewed project allowlist: {name}")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise RuntimeError(f"Unexpected binary content in public source: {name}") from None
    lower = text.lower()
    private_tokens = {str(Path.home()).lower(), Path.home().as_posix().lower()}
    if any(token in lower for token in private_tokens) or re.search(r"[a-z]:[\\/]users[\\/]", lower):
        raise RuntimeError(f"Private user path found: {name}")
    if any(re.search(pattern, text) for pattern in SECRET_PATTERNS):
        raise RuntimeError(f"Possible secret found: {name}")


def audit_git_files(staged: bool = False) -> int:
    command = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"] if staged else [
        "git", "ls-files", "--cached", "--others", "--exclude-standard", "-z",
    ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, check=True)
    names = sorted({name.decode("utf-8") for name in result.stdout.split(b"\0") if name})
    for name in names:
        ignored = subprocess.run(["git", "check-ignore", "--no-index", "--quiet", "--", name], cwd=ROOT)
        if ignored.returncode == 0:
            raise RuntimeError(f"An excluded local file is tracked or staged: {name}")
        if ignored.returncode != 1:
            raise RuntimeError("Git ignore validation failed.")
        if (ROOT / name).is_symlink():
            raise RuntimeError(f"Unexpected symlink in public source: {name}")
        content = subprocess.run(["git", "show", ":" + name], cwd=ROOT, capture_output=True, check=True).stdout if staged else (ROOT / name).read_bytes()
        audit_content(name, content)
    return len(names)


def check_code(code):
    if not isinstance(code, types.CodeType):
        return
    filename = code.co_filename
    if Path(filename).is_absolute() or re.match(r"^[A-Za-z]:", filename):
        raise RuntimeError("An absolute source path is embedded in a release code object.")
    for constant in code.co_consts:
        check_code(constant)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true", help="Audit exact staged blobs before committing")
    options = parser.parse_args()
    count = audit_git_files(staged=options.staged)
    print(f"Public {'index' if options.staged else 'source'} audit passed: {count} files.")
    if options.staged:
        return
    for executable in (ROOT / "release-local").glob("*-Portable.exe"):
        archive = CArchiveReader(str(executable))
        for name, metadata in archive.toc.items():
            if metadata[-1] == "s":
                check_code(marshal.loads(archive.extract(name)))
        embedded = archive.open_embedded_archive("PYZ.pyz")
        for name in embedded.toc:
            if name.startswith("youtube_saver"):
                check_code(embedded.extract(name))
        print("Portable EXE: no absolute application source paths.")
    for file in (ROOT / "release-local").glob("*"):
        result = subprocess.run(["git", "check-ignore", "--no-index", "--quiet", str(file.relative_to(ROOT))], cwd=ROOT)
        if result.returncode:
            raise RuntimeError(f"Release artifact is not Git-ignored: {file.name}")
    print("All release artifacts are ignored by Git.")


if __name__ == "__main__":
    main()
