# EasyClipper

简体中文 | [English](README.en.md)

使用 Python、PySide6 和本地 FFmpeg 的简易视频剪辑工具。支持拖入视频、播放和定位、预览选定片段、设置起止时间与视频目标码率、选择是否保留音频、导出 MP4，以及查看导出进度和取消导出。

## 启动

1. 将支持 `libx264` 和 AAC 编码的 `ffmpeg.exe` 放到本目录，也支持 `ffmpeg/bin/ffmpeg.exe`、`ffmpeg/ffmpeg.exe`、`bin/ffmpeg.exe` 或系统 PATH。不需要 ffprobe。
2. 在本目录运行：

   ```powershell
   uv sync
   uv run python main.py
   ```

   uv 自动管理项目的 `.venv` 虚拟环境和 Python。也可以双击 `run.bat` 启动。

### FFmpeg 文件放置

可以直接保留 FFmpeg 压缩包中的 `bin` 文件夹：

```text
EasyClipper/
├─ bin/
│  ├─ ffmpeg.exe
│  └─ 相关 DLL（如果有）
├─ easyclipper/
│  ├─ __init__.py
│  ├─ __main__.py
│  ├─ window.py
│  ├─ config.py
│  ├─ ffmpeg.py
│  ├─ i18n.py
│  └─ locales/
│     ├─ zh_CN.json
│     └─ en.json
├─ tests/
├─ main.py
├─ config.json          # 首次启动时生成
├─ pyproject.toml
├─ uv.lock
├─ README.md
├─ README.en.md
└─ run.bat
```

本工具不需要压缩包中的 `doc`、`presets` 文件夹，也不需要 `ffprobe.exe` 或 `ffplay.exe`。如果 `bin` 中有 DLL，请与 `ffmpeg.exe` 一起保留。

## 使用

窗口右上角的“界面语言 / Language”可即时切换简体中文和 English，无需重新启动。切换时会保留视频、截取时间和导出设置，导出过程中也可切换语言。

1. 将视频拖入窗口，或点击“打开视频”。
2. 播放或拖动进度条，在需要的画面点击“设为当前画面”，分别设置开始和结束时间。也可直接输入秒数，支持三位小数。例如 `90.5` 表示 1 分 30.5 秒。
3. 点击“预览选定片段”检查范围；普通“播放”按钮播放整个视频。
4. 设置视频目标码率，例如 `5000 kbps` 约为 `5 Mbps`。这是平均码率目标，实际码率会有浮动。提高码率不会提升原视频本身的清晰度。
5. 按需勾选音频，点击“导出 MP4”选择保存路径。

输出为 H.264 视频；保留音频时，将第一条音轨编码为 AAC 192 kbps，无音轨的视频仍可正常导出。不导出字幕。保持原始分辨率和帧率，奇数宽高会补齐到偶数。时间选择精度为毫秒，实际画面截取受视频帧间隔限制。预计文件大小约为“时长秒数 ×（视频码率 + 音频码率）÷ 8”，单位为 KB。

导出在后台运行，界面保持响应。编码先写入目标目录内的临时文件，成功后才替换目标文件；取消或编码失败不会覆盖已有目标文件。请正常关闭窗口，以便清理正在导出的临时文件。

预览使用 Qt Multimedia，可播放的格式取决于其解码支持。若文件预览失败，界面会显示原因。导出失败时可展开对话框中的详细 FFmpeg 日志。

## 配置保存

启动时会在项目目录（与 `run.bat` 同级）自动创建 `config.json`，下次启动会恢复上次使用的语言、视频目标码率和是否包含音频。修改这些选项后会自动保存，无需手动点击保存。视频文件、输出路径、播放位置和截取时间范围不会保存。

没有配置时默认使用英文。默认配置如下，也可以关闭程序后手动修改：

```json
{
  "language": "en",
  "bitrate_kbps": 5000,
  "include_audio": true
}
```

`language` 支持 `zh_CN` 和 `en`；`bitrate_kbps` 为 100–200000 的整数；`include_audio` 为 `true` 或 `false`。缺失或无效的配置项使用默认值，损坏的 JSON 会恢复默认配置。删除配置文件后，下次启动会重新创建。无法写入配置时，界面会显示提示，当前设置仍可使用。`config.json` 已加入 `.gitignore`，避免将个人配置上传到 GitHub。

配置读写与校验在 `easyclipper/config.py` 中实现。

## 语言包

界面文字保存在 `easyclipper/locales/zh_CN.json`（简体中文）和 `easyclipper/locales/en.json`（英文）中，由 `easyclipper/i18n.py` 加载。修改对应文件后重新启动即可应用。两个文件使用相同的键名；翻译时请保留 `{path}`、`{message}`、`{start}`、`{end}`、`{duration:.3f}` 等占位符。

FFmpeg 日志和操作系统或解码器返回的原始错误信息保留其原文。

## 代码结构与测试

`easyclipper/window.py` 负责界面和交互，`easyclipper/ffmpeg.py` 负责查找 FFmpeg 和构造导出参数。根目录的 `main.py` 是主程序入口，`run.bat` 通过 `uv run python main.py` 启动它。也支持 `uv run easyclipper` 或 `uv run python -m easyclipper`，这些入口共用 `easyclipper/__main__.py` 中的启动逻辑。

在项目目录运行测试：

```powershell
uv run python -m unittest discover -s tests -v
```
