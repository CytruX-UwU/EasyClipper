import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from shiboken6 import delete

from easyclipper.config import ConfigStore, Preferences
import easyclipper.window as ec


class ConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=ec.ROOT)
        self.folder = Path(self.directory.name)
        self.path = self.folder / "config.json"
        self.store = ConfigStore(self.path)
        self.windows = []

    def tearDown(self):
        for window in reversed(self.windows):
            self.app.removeTranslator(window.qt_translator)
            window.close()
            delete(window)
        self.directory.cleanup()

    def window(self):
        window = ec.Window(self.path)
        self.windows.append(window)
        return window

    def test_first_launch_creates_defaults_in_project_directory(self):
        with patch.object(ec, "ROOT", self.folder):
            window = ec.Window()
        self.windows.append(window)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), {
            "language": "en", "bitrate_kbps": 5000, "include_audio": True,
        })

    def test_settings_saved_immediately_and_restored_without_media(self):
        window = self.window()
        window.language_combo.setCurrentIndex(window.language_combo.findData("en"))
        window.bitrate.setValue(8000)
        window.include_audio.setChecked(False)
        window.source = Path("private-video.mp4")
        window.output = Path("private-output.mp4")
        window.duration_changed(10000)
        window.start.setValue(1.25)
        window.end.setValue(4.75)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), {
            "language": "en", "bitrate_kbps": 8000, "include_audio": False,
        })
        restored = self.window()
        self.assertEqual(restored.language, "en")
        self.assertEqual(restored.bitrate.value(), 8000)
        self.assertFalse(restored.include_audio.isChecked())
        self.assertIsNone(restored.source)
        self.assertIsNone(restored.output)
        self.assertEqual(restored.start.value(), 0)
        self.assertEqual(restored.end.value(), 0)
        self.assertFalse(restored.export_button.isEnabled())

    def test_invalid_configuration_uses_defaults(self):
        for data in ("{broken", "[]", "null", '{"language": [], "bitrate_kbps": true, "include_audio": "false"}',
                     '{"language": "unknown", "bitrate_kbps": 99}', '{"bitrate_kbps": 200001}'):
            with self.subTest(data=data):
                self.path.write_text(data, encoding="utf-8")
                self.assertEqual(self.store.load(), Preferences())
        self.path.write_text('{"language": "en", "bitrate_kbps": "5000", "include_audio": false}', encoding="utf-8-sig")
        self.assertEqual(self.store.load(), Preferences("en", 5000, False))

    def test_failed_atomic_write_preserves_previous_file(self):
        self.store.save(Preferences())
        previous = self.path.read_bytes()
        with patch("easyclipper.config.os.replace", side_effect=PermissionError("read only")):
            with self.assertRaises(PermissionError):
                self.store.save(Preferences("en", 8000, False))
        self.assertEqual(self.path.read_bytes(), previous)
        self.assertEqual(list(self.folder.glob(".easyclipper-config-*.tmp")), [])

    def test_save_error_is_visible_and_can_recover(self):
        window = self.window()
        with patch.object(window.config_store, "save", side_effect=PermissionError("read only")):
            window.bitrate.setValue(8000)
            window.language_combo.setCurrentIndex(window.language_combo.findData("en"))
            self.assertFalse(window.config_notice.isHidden())
            self.assertIn("Could not save preferences", window.config_notice.text())
            self.assertEqual(window.bitrate.value(), 8000)
            self.assertEqual(window.status_key, "initial")
        window.bitrate.setValue(9000)
        self.assertTrue(window.config_notice.isHidden())
        self.assertEqual(self.store.load().bitrate_kbps, 9000)


if __name__ == "__main__":
    unittest.main()
