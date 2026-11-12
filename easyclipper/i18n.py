"""JSON language packs for EasyClipper."""

from importlib.resources import files
import json

LANGUAGES = {"zh_CN": "简体中文", "en": "English"}


def load_language(code: str) -> dict[str, str]:
    if code not in LANGUAGES:
        raise ValueError(f"Unsupported language: {code}")
    return json.loads(files(__package__).joinpath("locales", f"{code}.json").read_text(encoding="utf-8"))
