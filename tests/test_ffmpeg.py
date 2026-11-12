from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import easyclipper.ffmpeg as ffmpeg


class FFmpegTests(unittest.TestCase):
    def test_project_bin_is_preferred_over_system_path(self):
        filename = "ffmpeg.exe" if ffmpeg.os.name == "nt" else "ffmpeg"
        with tempfile.TemporaryDirectory(dir=ffmpeg.ROOT) as directory:
            root = Path(directory)
            executable = root / "bin" / filename
            executable.parent.mkdir()
            executable.touch()
            with patch.object(ffmpeg, "ROOT", root), patch.object(ffmpeg.shutil, "which", return_value="system-ffmpeg"):
                self.assertEqual(ffmpeg.find_ffmpeg(), str(executable))
                (root / filename).touch()
                self.assertEqual(ffmpeg.find_ffmpeg(), str(root / filename))

    def test_export_arguments_preserve_range_bitrate_and_audio_choice(self):
        for audio in (False, True):
            with self.subTest(audio=audio):
                args = ffmpeg.export_args(Path("input video.mp4"), Path("output video.mp4"), 1.25, 3.5, 7000, audio)
                self.assertEqual(args[args.index("-ss") + 1], "1.250")
                self.assertEqual(args[args.index("-t") + 1], "3.500")
                self.assertEqual(args[args.index("-b:v") + 1], "7000k")
                self.assertEqual(args[-1], "output video.mp4")
                self.assertEqual("0:a:0?" in args, audio)
                self.assertEqual("-an" in args, not audio)


if __name__ == "__main__":
    unittest.main()
