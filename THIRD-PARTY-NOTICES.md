# Third-party components

YouTube Saver's application source is MIT licensed. Bundled tools retain their
own licenses; the combined binary distribution includes GPL components.

| Component | License | Official source |
| --- | --- | --- |
| yt-dlp executable and bundled dependencies | Unlicense / GPLv3+ components | https://github.com/yt-dlp/yt-dlp |
| FFmpeg and FFprobe GPL build | GPLv3+ | https://github.com/yt-dlp/FFmpeg-Builds |
| Deno | MIT and third-party notices | https://github.com/denoland/deno |
| Python | PSF and included notices | https://www.python.org/ |
| Tcl/Tk | BSD-style | https://www.tcl-lang.org/ |
| PyInstaller runtime | GPLv2+ with distribution exception | https://pyinstaller.org/ |

License texts are included in `licenses/` inside the packaged resources.
Exact tool versions, official release URLs and SHA-256 values are recorded in
`tools/manifest.json`. FFmpeg builds are produced with the upstream build recipes
at https://github.com/yt-dlp/FFmpeg-Builds and https://github.com/yt-dlp/FFmpeg-Builds/tree/master.
Retain the notices and supply corresponding source under the applicable GPL
terms when redistributing binaries. YouTube Saver is not affiliated with YouTube.
