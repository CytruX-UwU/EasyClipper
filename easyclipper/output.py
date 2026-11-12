"""Detect destination changes and publish completed exports."""

import os
from pathlib import Path

FileState = tuple[int, int, int, int, int, int]


class DestinationChanged(OSError):
    """The destination no longer matches the version approved by the user."""


def file_state(path: Path) -> FileState | None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def publish_output(temporary: Path, destination: Path, expected: FileState | None) -> None:
    if file_state(destination) != expected:
        raise DestinationChanged(str(destination))
    if expected is None:
        # Use a no-overwrite operation so a file created after the check is safe too.
        try:
            if os.name == "nt":
                os.rename(temporary, destination)
            else:
                os.link(temporary, destination)
        except FileExistsError as error:
            raise DestinationChanged(str(destination)) from error
        if os.name != "nt":
            temporary.unlink()
    else:
        os.replace(temporary, destination)
