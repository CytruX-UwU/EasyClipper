"""EasyClipper — local FFmpeg video clipping with a Qt preview."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile

from PySide6.QtCore import QLibraryInfo, QProcess, Qt, QTranslator, QUrl
from PySide6.QtGui import QCloseEvent, QDragEnterEvent, QDropEvent
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QMainWindow, QMessageBox, QProgressBar,
    QPushButton, QSlider, QSpinBox, QVBoxLayout, QWidget,
)

from . import ROOT
from .config import ConfigStore, Preferences
from .ffmpeg import export_args, find_ffmpeg
from .i18n import LANGUAGES, load_language
from .output import DestinationChanged, FileState, file_state, publish_output


def timestamp(milliseconds: int) -> str:
    seconds, ms = divmod(max(0, milliseconds), 1000)
    minutes, sec = divmod(seconds, 60)
    hours, minute = divmod(minutes, 60)
    return f"{hours:02}:{minute:02}:{sec:02}.{ms:03}"


class Window(QMainWindow):
    def __init__(self, config_path: Path | None = None) -> None:
        super().__init__()
        self.config_store = ConfigStore(config_path if config_path is not None else ROOT / "config.json")
        preferences = self.config_store.load()
        self.config_error = ""
        self.language = preferences.language
        self.messages = load_language(self.language)
        self.qt_translator = QTranslator(self)
        self.status_key = "initial"
        self.status_values: dict[str, object] = {}
        self.translated_widgets: list[tuple[QWidget, str]] = []
        self.resize(1000, 760)
        self.setAcceptDrops(True)
        self.source: Path | None = None
        self.duration = 0
        self.pending_range = False
        self.process: QProcess | None = None
        self.temp_output: Path | None = None
        self.output: Path | None = None
        self.output_state: FileState | None = None
        self.cancelled = False
        self.log = ""
        self.progress_buffer = ""
        self.export_duration = 0.0

        body = QWidget()
        self.setCentralWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(20, 16, 20, 16)
        language_row = QHBoxLayout()
        self.language_label = QLabel()
        self.language_combo = QComboBox()
        for code, name in LANGUAGES.items():
            self.language_combo.addItem(name, code)
        self.language_combo.setCurrentIndex(self.language_combo.findData(self.language))
        language_row.addStretch()
        language_row.addWidget(self.language_label)
        language_row.addWidget(self.language_combo)
        layout.addLayout(language_row)
        self.open_button = QPushButton()
        self.open_button.clicked.connect(self.choose_video)
        layout.addWidget(self.open_button)
        self.filename = QLabel()
        self.filename.setWordWrap(True)
        layout.addWidget(self.filename)

        self.video = QVideoWidget()
        self.video.setMinimumSize(400, 240)
        self.video.setStyleSheet("background: #16181d;")
        layout.addWidget(self.video, 1)
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(0.7)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video)
        self.player.durationChanged.connect(self.duration_changed)
        self.player.positionChanged.connect(self.position_changed)
        self.player.playbackStateChanged.connect(self.playback_changed)
        self.player.errorOccurred.connect(self.media_error)

        transport = QHBoxLayout()
        self.play_button = QPushButton(self.text("play"))
        self.play_button.clicked.connect(self.toggle_play)
        transport.addWidget(self.play_button)
        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.setRange(0, 0)
        self.seek.sliderMoved.connect(self.player.setPosition)
        self.seek.sliderReleased.connect(lambda: self.player.setPosition(self.seek.value()))
        transport.addWidget(self.seek, 1)
        self.clock = QLabel("00:00:00.000 / 00:00:00.000")
        transport.addWidget(self.clock)
        layout.addLayout(transport)

        self.settings = QWidget()
        form = QFormLayout(self.settings)
        self.start = self.time_input()
        self.end = self.time_input()
        for label, field, callback in (
            ("start", self.start, self.mark_start),
            ("end", self.end, self.mark_end),
        ):
            row = QHBoxLayout()
            row.addWidget(field)
            button = QPushButton()
            self.translated_widgets.append((button, "mark"))
            button.clicked.connect(callback)
            row.addWidget(button)
            text_label = QLabel()
            self.translated_widgets.append((text_label, label))
            form.addRow(text_label, row)
        self.bitrate = QSpinBox()
        self.bitrate.setRange(100, 200000)
        self.bitrate.setValue(preferences.bitrate_kbps)
        self.bitrate.setKeyboardTracking(False)
        self.bitrate.setSuffix(" kbps")
        self.bitrate.setSingleStep(500)
        bitrate_label = QLabel()
        self.translated_widgets.append((bitrate_label, "bitrate"))
        form.addRow(bitrate_label, self.bitrate)
        self.include_audio = QCheckBox(self.text("include_audio"))
        self.include_audio.setChecked(preferences.include_audio)
        audio_label = QLabel()
        self.translated_widgets.append((audio_label, "audio"))
        form.addRow(audio_label, self.include_audio)
        self.preview_range = QPushButton(self.text("preview"))
        self.preview_range.clicked.connect(self.play_range)
        form.addRow(self.preview_range)
        layout.addWidget(self.settings)
        self.start.valueChanged.connect(self.update_selection)
        self.end.valueChanged.connect(self.update_selection)
        self.selection = QLabel()
        layout.addWidget(self.selection)
        self.update_selection()

        actions = QHBoxLayout()
        self.export_button = QPushButton(self.text("export"))
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export)
        self.cancel_button = QPushButton(self.text("cancel"))
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_export)
        actions.addWidget(self.export_button)
        actions.addWidget(self.cancel_button)
        layout.addLayout(actions)
        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        self.status = QLabel(self.text("initial"))
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.config_notice = QLabel()
        self.config_notice.setWordWrap(True)
        self.config_notice.hide()
        layout.addWidget(self.config_notice)
        self.selection.setWordWrap(True)
        self.translated_widgets.extend([
            (self.language_label, "language"), (self.open_button, "open"),
            (self.include_audio, "include_audio"), (self.preview_range, "preview"),
            (self.export_button, "export"), (self.cancel_button, "cancel"),
        ])
        self.language_combo.currentIndexChanged.connect(self.change_language)
        self.bitrate.valueChanged.connect(self.save_config)
        self.include_audio.toggled.connect(self.save_config)
        self.change_language()

    def save_config(self, _value: object = None) -> None:
        preferences = Preferences(
            language=self.language,
            bitrate_kbps=self.bitrate.value(),
            include_audio=self.include_audio.isChecked(),
        )
        try:
            self.config_store.save(preferences)
        except OSError as error:
            self.config_error = str(error)
        else:
            self.config_error = ""
        self.config_notice.setText(
            self.text("config_save_error", message=self.config_error) if self.config_error else "")
        self.config_notice.setVisible(bool(self.config_error))

    def text(self, key: str, **values: object) -> str:
        return self.messages[key].format(**values)

    def set_status(self, key: str, **values: object) -> None:
        self.status_key, self.status_values = key, values
        self.status.setText(self.text(key, **values))

    def change_language(self, _index: int = 0) -> None:
        self.language = self.language_combo.currentData()
        self.messages = load_language(self.language)
        app = QApplication.instance()
        app.removeTranslator(self.qt_translator)
        if self.language == "zh_CN":
            if self.qt_translator.load("qtbase_zh_CN", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
                app.installTranslator(self.qt_translator)
        self.setWindowTitle(self.text("title"))
        for widget, key in self.translated_widgets:
            widget.setText(self.text(key))
        for field in (self.start, self.end):
            field.setSuffix(self.text("seconds"))
        if self.source is None:
            self.filename.setText(self.text("no_video"))
        self.playback_changed(self.player.playbackState())
        self.update_selection()
        self.set_status(self.status_key, **self.status_values)
        self.save_config()

    def warning(self, title: str, message: str) -> None:
        dialog = QMessageBox(QMessageBox.Icon.Warning, self.text(title), message,
                             QMessageBox.StandardButton.Ok, self)
        dialog.button(QMessageBox.StandardButton.Ok).setText(self.text("ok"))
        dialog.exec()

    def question(self, title: str, message: str) -> bool:
        dialog = QMessageBox(QMessageBox.Icon.Question, self.text(title), message,
                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, self)
        dialog.button(QMessageBox.StandardButton.Yes).setText(self.text("yes"))
        dialog.button(QMessageBox.StandardButton.No).setText(self.text("no"))
        dialog.setDefaultButton(QMessageBox.StandardButton.No)
        return dialog.exec() == QMessageBox.StandardButton.Yes

    @staticmethod
    def time_input() -> QDoubleSpinBox:
        field = QDoubleSpinBox()
        field.setDecimals(3)
        field.setRange(0, 0)
        field.setSingleStep(0.1)
        return field

    def choose_video(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, self.text("choose_video"), "", self.text("video_filter"),
            options=QFileDialog.Option.DontUseNativeDialog)
        if filename:
            self.load_video(Path(filename))

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self.process is None and event.mimeData().hasUrls():
            if any(url.isLocalFile() and Path(url.toLocalFile()).is_file()
                   for url in event.mimeData().urls()):
                event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        if self.process is not None:
            return
        for url in event.mimeData().urls():
            if url.isLocalFile() and Path(url.toLocalFile()).is_file():
                self.load_video(Path(url.toLocalFile()))
                event.acceptProposedAction()
                break

    def load_video(self, path: Path) -> None:
        self.player.stop()
        self.pending_range = False
        self.source = path.resolve()
        self.duration = 0
        self.start.setMaximum(0)
        self.end.setMaximum(0)
        self.seek.setRange(0, 0)
        self.export_button.setEnabled(False)
        self.filename.setText(str(self.source))
        self.set_status("loading")
        self.player.setSource(QUrl.fromLocalFile(str(self.source)))

    def duration_changed(self, duration: int) -> None:
        self.duration = duration
        self.seek.setRange(0, duration)
        self.start.setMaximum(duration / 1000)
        self.end.setMaximum(duration / 1000)
        self.end.setValue(duration / 1000)
        self.export_button.setEnabled(duration > 0 and self.process is None)
        if duration > 0:
            self.set_status("loaded")
        self.position_changed(self.player.position())

    def position_changed(self, position: int) -> None:
        if not self.seek.isSliderDown():
            self.seek.setValue(position)
        self.clock.setText(f"{timestamp(position)} / {timestamp(self.duration)}")
        if self.pending_range and position >= round(self.end.value() * 1000):
            self.pending_range = False
            self.player.pause()

    def playback_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        self.play_button.setText(self.text("pause") if state == QMediaPlayer.PlaybackState.PlayingState else self.text("play"))

    def toggle_play(self) -> None:
        self.pending_range = False
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def mark_start(self) -> None:
        self.start.setValue(self.player.position() / 1000)

    def mark_end(self) -> None:
        self.end.setValue(self.player.position() / 1000)

    def update_selection(self) -> None:
        if hasattr(self, "selection"):
            length = self.end.value() - self.start.value()
            self.selection.setText(self.text(
                "selection", start=timestamp(round(self.start.value() * 1000)),
                end=timestamp(round(self.end.value() * 1000)), duration=length))

    def valid_range(self) -> bool:
        if self.source is None or self.duration <= 0:
            self.warning("not_loaded", self.text("open_first"))
            return False
        if not 0 <= self.start.value() < self.end.value() <= self.duration / 1000:
            self.warning("invalid_range", self.text("range_error"))
            return False
        return True

    def play_range(self) -> None:
        if self.valid_range():
            self.player.pause()
            self.player.setPosition(round(self.start.value() * 1000))
            self.pending_range = True
            self.player.play()

    def media_error(self, _error: QMediaPlayer.Error, message: str) -> None:
        self.set_status("preview_error", message=message)
        self.export_button.setEnabled(False)

    def export(self) -> None:
        if not self.valid_range() or self.process is not None:
            return
        executable = find_ffmpeg()
        if not executable:
            self.warning("missing_ffmpeg", self.text("ffmpeg_help"))
            return
        assert self.source is not None
        filename, _ = QFileDialog.getSaveFileName(
            self, self.text("export_video"),
            str(self.source.with_name(self.source.stem + "_clip.mp4")),
            self.text("mp4_filter"), options=QFileDialog.Option.DontUseNativeDialog)
        if not filename:
            return
        output = Path(filename).with_suffix(".mp4").resolve()
        if output == self.source or (output.exists() and os.path.samefile(output, self.source)):
            self.warning("cannot_export", self.text("same_path"))
            return
        try:
            output_state = file_state(output)
        except OSError as error:
            self.warning("create_failed", str(error))
            return
        if output_state is not None:
            if not self.question("overwrite", self.text("overwrite_question", path=output)):
                return
        try:
            handle, name = tempfile.mkstemp(prefix=".easyclipper-", suffix=".partial.mp4", dir=output.parent)
            os.close(handle)
        except OSError as error:
            self.warning("create_failed", str(error))
            return
        self.temp_output = Path(name)
        self.output = output
        self.output_state = output_state
        self.export_duration = self.end.value() - self.start.value()
        self.log = ""
        self.progress_buffer = ""
        self.cancelled = False
        self.progress.setValue(0)
        self.player.pause()
        self.pending_range = False
        self.settings.setEnabled(False)
        self.open_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        process = QProcess(self)
        self.process = process
        process.readyReadStandardError.connect(self.read_log)
        process.readyReadStandardOutput.connect(self.read_progress)
        process.finished.connect(self.export_finished)
        process.errorOccurred.connect(self.process_error)
        self.set_status("exporting")
        process.start(executable, export_args(self.source, self.temp_output, self.start.value(),
                                            self.export_duration, self.bitrate.value(), self.include_audio.isChecked()))

    def read_log(self) -> None:
        if self.process:
            self.log = (self.log + bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace"))[-16000:]

    def read_progress(self) -> None:
        if not self.process:
            return
        self.progress_buffer += bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        while "\n" in self.progress_buffer:
            line, self.progress_buffer = self.progress_buffer.split("\n", 1)
            key, _, value = line.strip().partition("=")
            if key == "out_time_us":
                try:
                    percent = int(int(value) / 1_000_000 / self.export_duration * 100)
                    self.progress.setValue(min(99, max(0, percent)))
                except ValueError:
                    pass

    def process_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart and self.process:
            self.log += self.process.errorString()
            self.export_finished(-1, QProcess.ExitStatus.CrashExit)

    def export_finished(self, code: int, status: QProcess.ExitStatus) -> None:
        if self.process is None:
            return
        self.read_log()
        self.read_progress()
        process = self.process
        self.process = None
        process.deleteLater()
        self.settings.setEnabled(True)
        self.open_button.setEnabled(True)
        self.export_button.setEnabled(self.duration > 0)
        self.cancel_button.setEnabled(False)
        success = code == 0 and status == QProcess.ExitStatus.NormalExit and not self.cancelled
        if success and self.temp_output and self.output:
            try:
                while True:
                    try:
                        publish_output(self.temp_output, self.output, self.output_state)
                        break
                    except DestinationChanged:
                        # Snapshot before the modal dialog; check again after confirmation.
                        current_state = file_state(self.output)
                        if not self.question("output_changed_title", self.text("output_changed_question", path=self.output)):
                            self.progress.setValue(100)
                            self.set_status("output_kept", path=self.temp_output)
                            return
                        self.output_state = current_state
            except OSError as error:
                self.set_status("save_error_status", path=self.temp_output)
                self.warning("save_failed", str(error))
                return
            self.progress.setValue(100)
            self.set_status("exported", path=self.output)
        else:
            if self.temp_output:
                try:
                    self.temp_output.unlink(missing_ok=True)
                except OSError:
                    pass
            self.progress.setValue(0)
            self.set_status("cancelled" if self.cancelled else "failed_status")
            if not self.cancelled:
                message = QMessageBox(self)
                message.setWindowTitle(self.text("failed_title"))
                message.setText(self.text("failed_message"))
                message.setDetailedText(self.log or self.text("no_log"))
                message.setIcon(QMessageBox.Icon.Warning)
                message.exec()

    def cancel_export(self) -> None:
        if self.process:
            self.cancelled = True
            self.cancel_button.setEnabled(False)
            self.set_status("cancelling")
            self.process.kill()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.process:
            if not self.question("exporting_title", self.text("close_question")):
                event.ignore()
                return
            self.cancel_export()
            if self.process:
                self.process.waitForFinished(3000)
        self.player.stop()
        event.accept()
