import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from pathlib import Path
from string import Formatter
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from shiboken6 import delete

import easyclipper.window as ec
from easyclipper.i18n import load_language


class LanguageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=ec.ROOT)
        self.window = ec.Window(Path(self.directory.name) / "config.json")

    def tearDown(self):
        self.app.removeTranslator(self.window.qt_translator)
        self.window.close()
        delete(self.window)
        self.directory.cleanup()

    def test_packs_have_matching_keys_and_placeholders(self):
        chinese, english = load_language("zh_CN"), load_language("en")
        self.assertEqual(chinese.keys(), english.keys())
        formatter = Formatter()
        for key in chinese:
            def fields(text):
                return {(field, spec, conversion) for _, field, spec, conversion
                        in formatter.parse(text) if field is not None}
            with self.subTest(key=key):
                self.assertTrue(chinese[key])
                self.assertTrue(english[key])
                self.assertEqual(fields(chinese[key]), fields(english[key]))

    def test_switch_preserves_inputs_and_renders_dynamic_state(self):
        w = self.window
        self.assertEqual(w.open_button.text(), load_language("en")["open"])
        w.source = Path("example.mp4")
        w.filename.setText(str(w.source))
        w.duration_changed(10000)
        w.start.setValue(1.25)
        w.end.setValue(4.75)
        w.bitrate.setValue(7000)
        w.include_audio.setChecked(False)
        w.progress.setValue(42)
        w.set_status("exported", path=Path("result.mp4"))
        for language in ("en", "zh_CN", "en"):
            w.language_combo.setCurrentIndex(w.language_combo.findData(language))
            pack = load_language(language)
            self.assertEqual(w.windowTitle(), pack["title"])
            for widget, key in w.translated_widgets:
                self.assertEqual(widget.text(), pack[key])
            self.assertEqual(w.start.value(), 1.25)
            self.assertEqual(w.end.value(), 4.75)
            self.assertEqual(w.start.suffix(), pack["seconds"])
            self.assertEqual(w.bitrate.value(), 7000)
            self.assertFalse(w.include_audio.isChecked())
            self.assertEqual(w.progress.value(), 42)
            self.assertEqual(w.filename.text(), "example.mp4")
            self.assertEqual(w.status.text(), pack["exported"].format(path="result.mp4"))
            self.assertIn("3.500", w.selection.text())

    def test_dialogs_follow_selected_language(self):
        w = self.window
        for language in ("en", "zh_CN"):
            w.language_combo.setCurrentIndex(w.language_combo.findData(language))
            pack = load_language(language)
            def inspect(dialog):
                self.assertEqual(dialog.windowTitle(), pack["overwrite"])
                self.assertEqual(dialog.button(QMessageBox.StandardButton.Yes).text(), pack["yes"])
                self.assertEqual(dialog.button(QMessageBox.StandardButton.No).text(), pack["no"])
                return QMessageBox.StandardButton.No
            with patch.object(QMessageBox, "exec", inspect):
                self.assertFalse(w.question("overwrite", w.text("overwrite_question", path="out.mp4")))
            with patch.object(QFileDialog, "getOpenFileName", return_value=("", "")) as choose:
                w.choose_video()
                self.assertEqual(choose.call_args.args[1], pack["choose_video"])
                self.assertEqual(choose.call_args.args[3], pack["video_filter"])

    def test_switch_during_asynchronous_export(self):
        w = self.window
        with tempfile.TemporaryDirectory(dir=ec.ROOT) as directory:
            folder = Path(directory)
            w.source = folder / "input.mp4"
            w.source.write_bytes(b"source")
            output = folder / "output.mp4"
            w.duration_changed(10000)
            w.start.setValue(1)
            w.end.setValue(4)
            script = ("import pathlib,sys,time; time.sleep(0.2); "
                      "pathlib.Path(sys.argv[1]).write_bytes(b'encoded'); "
                      "print('out_time_us=3000000', flush=True)")
            with patch.object(ec, "find_ffmpeg", return_value=sys.executable), \
                 patch.object(QFileDialog, "getSaveFileName", return_value=(str(output), "")), \
                 patch.object(ec, "export_args", side_effect=lambda *args: ["-c", script, str(args[1])]):
                w.export()
                process = w.process
                w.language_combo.setCurrentIndex(w.language_combo.findData("en"))
                self.assertIs(w.process, process)
                self.assertEqual(w.status.text(), "Exporting…")
                self.assertFalse(w.settings.isEnabled())
                deadline = time.monotonic() + 10
                while w.process is not None and time.monotonic() < deadline:
                    QTest.qWait(20)
                if w.process is not None:
                    w.cancel_export()
                    w.process.waitForFinished(3000)
                    self.fail("Export timed out")
            self.assertEqual(output.read_bytes(), b"encoded")
            self.assertEqual(w.progress.value(), 100)
            self.assertEqual(w.status.text(), f"Export complete: {output}")
            w.language_combo.setCurrentIndex(w.language_combo.findData("zh_CN"))
            self.assertEqual(w.status.text(), load_language("zh_CN")["exported"].format(path=output))


if __name__ == "__main__":
    unittest.main()
