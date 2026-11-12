# EasyClipper

[简体中文](README.md) | English

A simple video clipping tool built with Python, PySide6, and local FFmpeg. Drag in a video, play and seek through it, preview a selected range, set start and end times and the target video bitrate, choose whether to include audio, and export to MP4 with progress tracking and cancellation.

Use the “界面语言 / Language” selector at the top right to switch instantly between Simplified Chinese and English. No restart is needed. Switching preserves the loaded video, selected time range, and export settings, and also works during export.

## Getting started

1. Place an `ffmpeg.exe` build with `libx264` and AAC encoding support in the project directory. The app also checks `ffmpeg/bin/ffmpeg.exe`, `ffmpeg/ffmpeg.exe`, `bin/ffmpeg.exe`, and the system PATH. ffprobe is not required.
2. With uv installed, run these commands from the project directory:

   ```powershell
   uv sync
   uv run python main.py
   ```

   uv manages Python and the project's `.venv` virtual environment. On Windows, you can also double-click `run.bat` to launch the app.

### FFmpeg file layout

You can keep the `bin` folder from the FFmpeg archive directly:

```text
EasyClipper/
├─ bin/
│  ├─ ffmpeg.exe
│  └─ Required DLLs (if present)
├─ easyclipper/
│  ├─ __init__.py
│  ├─ __main__.py
│  ├─ window.py
│  ├─ config.py
│  ├─ ffmpeg.py
│  ├─ output.py
│  ├─ i18n.py
│  └─ locales/
│     ├─ zh_CN.json
│     └─ en.json
├─ tests/
├─ main.py
├─ config.json          # Created on first launch
├─ pyproject.toml
├─ uv.lock
├─ README.md
├─ README.en.md
└─ run.bat
```

The archive's `doc` and `presets` folders are not required. Neither are `ffprobe.exe` and `ffplay.exe`. If the `bin` folder contains DLLs, keep them alongside `ffmpeg.exe`.

## Usage

1. Drag a video into the window, or click “打开视频” (Open video).
2. Play the video or move the seek slider. Click “设为当前画面” (Set to current frame) beside each time field to set the start and end points. You can also enter times in seconds with three decimal places. For example, `90.5` means 1 minute and 30.5 seconds.
3. Click “预览选定片段” (Preview selected clip) to check the selected range. The regular “播放” (Play) button plays the full video.
4. Set the target video bitrate. For example, `5000 kbps` is approximately `5 Mbps`. This is an average bitrate target; the actual bitrate may vary. Increasing it cannot improve the source video's original quality.
5. Choose whether to include audio, then click “导出 MP4” (Export MP4) and select a destination.

The output uses H.264 video. When audio is included, the first audio track is encoded as AAC at 192 kbps; videos without an audio track can still be exported. Subtitles are omitted. The original resolution and frame rate are preserved, with odd frame dimensions padded to even numbers. Time fields accept millisecond precision, while the actual cut is limited by video frame intervals. Approximate file size in KB is “duration in seconds × (video bitrate + audio bitrate in kbps) ÷ 8.”

Exports run in the background so the interface stays responsive. Encoding writes to a temporary file in the destination directory, and replaces the destination file only after encoding succeeds. Cancellation or encoding failure leaves any existing destination file intact. Close the app normally so it can clean up temporary files from an active export.

Before saving, the app checks whether the destination was created, modified, or removed during export. Changes require confirmation again. Declining preserves the destination and shows the encoded video's temporary file path so you can save it manually. New destinations use a no-overwrite filesystem operation to protect files created after the check.

Preview playback uses Qt Multimedia, so supported formats depend on its decoding capabilities. Preview errors appear in the interface. If an export fails, expand the error dialog to view the detailed FFmpeg log.

## Saved preferences

On startup, the app automatically creates `config.json` in the project directory, next to `run.bat`. It restores the last language, target video bitrate, and audio inclusion setting on the next launch. Changes to these options are saved automatically. Video files, output paths, playback position, and clip time ranges are never saved.

The app defaults to English when no configuration is available. The default configuration is shown below. You can also edit it manually while the app is closed:

```json
{
  "language": "en",
  "bitrate_kbps": 5000,
  "include_audio": true
}
```

`language` accepts `zh_CN` or `en`; `bitrate_kbps` must be an integer from 100 to 200000; `include_audio` is `true` or `false`. Missing or invalid fields use their defaults, and malformed JSON resets the configuration to defaults. Deleting the file recreates it on the next launch. If saving fails, a message appears in the interface and the current settings remain usable. `config.json` is excluded by `.gitignore` to keep personal preferences out of GitHub.

Configuration storage and validation are implemented separately in `easyclipper/config.py`.

Configuration files are limited to 64 KiB. Oversized files, excessive nesting, invalid UTF-8, and malformed JSON fall back to defaults so the app can still start.

## Language packs

Interface text is stored in `easyclipper/locales/zh_CN.json` (Simplified Chinese) and `easyclipper/locales/en.json` (English), and loaded by `easyclipper/i18n.py`. Restart the app after editing a pack. Both files use the same keys. Keep placeholders such as `{path}`, `{message}`, `{start}`, `{end}`, and `{duration:.3f}` intact when translating.

FFmpeg logs and raw errors returned by the operating system or decoder remain in their original language.

## Code structure and tests

`easyclipper/window.py` handles the interface and interactions. `easyclipper/ffmpeg.py` locates FFmpeg and builds export arguments. `easyclipper/output.py` checks for destination changes and saves encoded results. The root-level `main.py` is the main entry point, launched by `run.bat` using `uv run python main.py`. You can also use `uv run easyclipper` or `uv run python -m easyclipper`. All entry points share the startup logic in `easyclipper/__main__.py`.

Run tests from the project directory:

```powershell
uv run python -m unittest discover -s tests -v
```
