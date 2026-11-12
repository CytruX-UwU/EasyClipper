"""Validated preferences and atomic JSON storage; no media history is stored."""

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import tempfile

from .i18n import LANGUAGES


@dataclass
class Preferences:
    language: str = "en"
    bitrate_kbps: int = 5000
    include_audio: bool = True


class ConfigStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> Preferences:
        preferences = Preferences()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return preferences
        if not isinstance(data, dict):
            return preferences
        language = data.get("language")
        if isinstance(language, str) and language in LANGUAGES:
            preferences.language = language
        bitrate = data.get("bitrate_kbps")
        if type(bitrate) is int and 100 <= bitrate <= 200000:
            preferences.bitrate_kbps = bitrate
        audio = data.get("include_audio")
        if type(audio) is bool:
            preferences.include_audio = audio
        return preferences

    def save(self, preferences: Preferences) -> None:
        """Replace only after the complete file is written; propagate I/O failures."""
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent,
                prefix=".easyclipper-config-", suffix=".tmp", delete=False,
            ) as stream:
                temporary = Path(stream.name)
                json.dump(asdict(preferences), stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
