from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable

TAGS = [
    "-SourceFile", "-DateTimeOriginal", "-CreateDate", "-Make", "-Model", "-SerialNumber", "-InternalSerialNumber",
    "-LensModel", "-LensID", "-FocalLength", "-FocalLengthIn35mmFormat", "-FNumber", "-ExposureTime", "-ShutterSpeed",
    "-ISO", "-ExposureCompensation", "-ImageWidth", "-ImageHeight", "-Orientation", "-GPSLatitude", "-GPSLongitude",
    "-Rating", "-Subject", "-Keywords",
]


def find_exiftool() -> str:
    override = os.environ.get("PHOTOEXIF_EXIFTOOL")
    if override and Path(override).exists():
        return override
    packaged = Path(__file__).resolve().parents[1] / "vendor" / "exiftool" / "exiftool"
    if packaged.exists():
        return str(packaged)
    found = shutil.which("exiftool")
    if found:
        return found
    raise RuntimeError("ExifTool not found. Install it or set PHOTOEXIF_EXIFTOOL.")


def read_metadata(paths: Iterable[Path]) -> list[dict]:
    items = [str(path) for path in paths]
    if not items:
        return []
    cmd = [find_exiftool(), "-json", "-n", "-charset", "filename=UTF8", *TAGS, *items]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip() or "ExifTool failed")
    try:
        return json.loads(result.stdout.decode("utf-8", errors="replace") or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid ExifTool JSON: {exc}") from exc
