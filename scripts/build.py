"""Build local-only Windows artifacts with PyInstaller and Inno Setup."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / ".build"
RELEASE = ROOT / "release-local"


def verify_tools():
    manifest = json.loads((BUILD / "tools" / "manifest.json").read_text(encoding="utf-8"))
    for package in manifest:
        for name, expected in package["files"].items():
            with (BUILD / "tools" / name).open("rb") as source:
                actual = hashlib.file_digest(source, "sha256").hexdigest()
            if actual != expected:
                raise RuntimeError(f"Tool integrity check failed: {name}")


def freeze(name, mode, destination):
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", mode,
               "--noupx", "--name", name, "--paths", str(ROOT / "src"),
               "--icon", str(ROOT / "assets" / "desktop.ico"), "--version-file", str(ROOT / "scripts" / "windows-version.txt"),
               "--add-data", f"{ROOT / 'assets'};assets", "--add-data", f"{BUILD / 'tools'};tools",
               "--add-data", f"{ROOT / 'docs' / 'licenses'};licenses",
               "--add-data", f"{ROOT / 'LICENSE'};.", "--add-data", f"{ROOT / 'THIRD-PARTY-NOTICES.md'};.",
               "--distpath", str(destination), "--workpath", str(BUILD / "work" / name),
               "--specpath", str(BUILD / "specs"), str(ROOT / "run.py")]
    subprocess.run(command, check=True, cwd=ROOT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iscc", type=Path, required=True, help="Path to the official Inno Setup compiler")
    parser.add_argument("--installer-only", action="store_true", help="Rebuild setup using the existing app payload")
    options = parser.parse_args()
    verify_tools()
    RELEASE.mkdir(exist_ok=True)
    payload = BUILD / "payload" / "YouTube Saver"
    if options.installer_only:
        if not (payload / "YouTube Saver.exe").is_file():
            raise RuntimeError("Build the app payload before using --installer-only.")
    else:
        freeze("YouTube Saver", "--onedir", BUILD / "payload")
        shutil.copy2(ROOT / "THIRD-PARTY-NOTICES.md", payload)
        shutil.copy2(ROOT / "LICENSE", payload)
        freeze("YouTube-Saver-1.0.0-Portable", "--onefile", RELEASE)
    subprocess.run([str(options.iscc.resolve()), f"/DPayloadDir={payload}", f"/DReleaseDir={RELEASE}",
                    str(ROOT / "scripts" / "installer.iss")], check=True, cwd=ROOT)
    hashes = []
    for file in sorted(RELEASE.glob("*.exe")):
        with file.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        hashes.append(f"{digest}  {file.name}")
    (RELEASE / "SHA256SUMS.txt").write_text("\n".join(hashes) + "\n", encoding="utf-8")
    shutil.copy2(ROOT / "docs" / "RELEASE.txt", RELEASE / "RELEASE.txt")
    print("Build complete. All artifacts are in the Git-ignored release-local folder.")


if __name__ == "__main__":
    main()
