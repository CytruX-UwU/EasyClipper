import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication
from shiboken6 import delete

from easyclipper import ROOT
import easyclipper.output as output
from easyclipper.window import Window


class OutputTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=ROOT)
        self.folder = Path(self.directory.name)
        self.temporary = self.folder / "encoded.partial.mp4"
        self.destination = self.folder / "destination.mp4"
        self.temporary.write_bytes(b"encoded")

    def tearDown(self):
        self.directory.cleanup()

    def test_new_and_approved_existing_destinations_can_be_saved(self):
        self.destination.write_bytes(b"approved version")
        output.publish_output(self.temporary, self.destination, output.file_state(self.destination))
        self.assertEqual(self.destination.read_bytes(), b"encoded")
        self.assertFalse(self.temporary.exists())
        new_destination = self.folder / "new.mp4"
        self.temporary.write_bytes(b"second export")
        output.publish_output(self.temporary, new_destination, None)
        self.assertEqual(new_destination.read_bytes(), b"second export")

    def test_file_created_during_encoding_is_not_overwritten(self):
        self.destination.write_bytes(b"another process")
        with self.assertRaises(output.DestinationChanged):
            output.publish_output(self.temporary, self.destination, None)
        self.assertEqual(self.destination.read_bytes(), b"another process")
        self.assertTrue(self.temporary.exists())

    def test_modified_or_removed_destination_requires_confirmation(self):
        self.destination.write_bytes(b"approved version")
        approved = output.file_state(self.destination)
        self.destination.write_bytes(b"modified version with different size")
        with self.assertRaises(output.DestinationChanged):
            output.publish_output(self.temporary, self.destination, approved)
        self.assertEqual(self.destination.read_bytes(), b"modified version with different size")
        self.destination.unlink()
        with self.assertRaises(output.DestinationChanged):
            output.publish_output(self.temporary, self.destination, approved)
        self.assertTrue(self.temporary.exists())

    def test_file_created_after_final_check_is_not_overwritten(self):
        # Simulate creation between the existence check and the filesystem operation.
        def raced_state(_path):
            self.destination.write_bytes(b"racing file")
            return None
        with patch.object(output, "file_state", side_effect=raced_state):
            with self.assertRaises(output.DestinationChanged):
                output.publish_output(self.temporary, self.destination, None)
        self.assertEqual(self.destination.read_bytes(), b"racing file")
        self.assertTrue(self.temporary.exists())

    def test_declining_conflict_preserves_both_files(self):
        app = QApplication.instance() or QApplication([])
        window = Window(self.folder / "config.json")
        try:
            window.output = self.destination
            window.temp_output = self.temporary
            window.output_state = None
            window.export_duration = 1
            window.process = QProcess(window)
            self.destination.write_bytes(b"another process")
            with patch.object(window, "question", return_value=False) as question:
                window.export_finished(0, QProcess.ExitStatus.NormalExit)
            self.assertEqual(question.call_args.args[0], "output_changed_title")
            self.assertEqual(self.destination.read_bytes(), b"another process")
            self.assertEqual(self.temporary.read_bytes(), b"encoded")
            self.assertEqual(window.status_key, "output_kept")
        finally:
            app.removeTranslator(window.qt_translator)
            window.close()
            delete(window)

    def test_changes_during_confirmation_are_checked_again(self):
        app = QApplication.instance() or QApplication([])
        window = Window(self.folder / "config.json")
        try:
            window.output = self.destination
            window.temp_output = self.temporary
            window.output_state = None
            window.export_duration = 1
            window.process = QProcess(window)
            self.destination.write_bytes(b"another process")
            answers = iter((True, False))
            def answer(*_args):
                response = next(answers)
                if response:
                    self.destination.write_bytes(b"changed again while confirming")
                return response
            with patch.object(window, "question", side_effect=answer) as question:
                window.export_finished(0, QProcess.ExitStatus.NormalExit)
            self.assertEqual(question.call_count, 2)
            self.assertEqual(self.destination.read_bytes(), b"changed again while confirming")
            self.assertTrue(self.temporary.exists())
        finally:
            app.removeTranslator(window.qt_translator)
            window.close()
            delete(window)


if __name__ == "__main__":
    unittest.main()
