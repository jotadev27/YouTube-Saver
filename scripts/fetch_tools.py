"""Fetch only official tools; reject downloads without matching SHA-256."""
import concurrent.futures
import hashlib
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".build" / "tools"
PACKAGES = (
    ("yt-dlp/yt-dlp", "latest", "yt-dlp.exe", ("yt-dlp.exe",)),
    ("denoland/deno", "latest", "deno-x86_64-pc-windows-msvc.zip", ("deno.exe",)),
    ("yt-dlp/FFmpeg-Builds", "tags/latest", "ffmpeg-master-latest-win64-gpl.zip", ("ffmpeg.exe", "ffprobe.exe")),
)


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "YouTubeSaver-build"})
    return urllib.request.urlopen(request, timeout=60)


def install(package):
    repo, release, name, executables = package
    with fetch(f"https://api.github.com/repos/{repo}/releases/{release}") as response:
        metadata = json.load(response)
    asset = next(item for item in metadata["assets"] if item["name"] == name)
    expected = asset.get("digest", "")
    if not expected or not expected.startswith("sha256:"):
        raise RuntimeError(f"No SHA-256 published for {name}; download refused.")
    url = asset["browser_download_url"]
    if not url.startswith(f"https://github.com/{repo}/releases/download/"):
        raise RuntimeError("Unexpected download origin.")
    temporary = TOOLS / (name + ".download")
    digest = hashlib.sha256()
    print(f"Downloading {name}...", flush=True)
    try:
        with fetch(url) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                digest.update(chunk)
                output.write(chunk)
        if "sha256:" + digest.hexdigest() != expected:
            raise RuntimeError(f"SHA-256 mismatch for {name}; file rejected.")
        files = {}
        if name.endswith(".zip"):
            with zipfile.ZipFile(temporary) as archive:
                for executable in executables:
                    matches = [item for item in archive.infolist() if Path(item.filename).name == executable]
                    if len(matches) != 1:
                        raise RuntimeError(f"Missing or ambiguous {executable} in archive.")
                    target = TOOLS / executable
                    with archive.open(matches[0]) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
                    files[executable] = hashlib.file_digest(target.open("rb"), "sha256").hexdigest()
        else:
            temporary.replace(TOOLS / name)
            files[name] = digest.hexdigest()
        print(f"Verified {name}", flush=True)
        return {"project": repo, "version": metadata["tag_name"], "url": url,
                "archive_sha256": digest.hexdigest(), "files": files}
    finally:
        temporary.unlink(missing_ok=True)


def main():
    TOOLS.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        manifest = list(executor.map(install, PACKAGES))
    (TOOLS / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
