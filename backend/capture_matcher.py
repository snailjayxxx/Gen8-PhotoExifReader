from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable

EDITED_DEFAULT_SUFFIXES = (
    "-edit", "_edit", "-edited", "_edited", "-修图", "_修图", "-修圖", "_修圖", "-lr", "_lr", "-final", "_final"
)


def _contains_keyword(value: str, keywords: Iterable[str]) -> bool:
    lowered = value.casefold()
    return any(keyword.casefold() in lowered for keyword in keywords if keyword)


def classify_role(path: Path, raw_extensions: set[str], edited_keywords: list[str], jpeg_keywords: list[str]) -> str:
    ext = path.suffix.casefold()
    parents = [part for part in path.parts[:-1]]
    if _contains_keyword("/".join(parents), edited_keywords):
        return "edited"
    if ext in raw_extensions:
        return "raw"
    if ext in {".jpg", ".jpeg", ".heic", ".heif", ".tif", ".tiff"}:
        if _contains_keyword("/".join(parents), jpeg_keywords):
            return "camera_jpeg"
        return "jpeg"
    return "image"


def normalized_stem(filename: str, edited_suffixes: Iterable[str] = EDITED_DEFAULT_SUFFIXES) -> str:
    stem = Path(filename).stem.strip()
    lowered = stem.casefold()
    changed = True
    while changed:
        changed = False
        for suffix in edited_suffixes:
            token = suffix.casefold()
            if token and lowered.endswith(token):
                stem = stem[: -len(suffix)].rstrip("- _")
                lowered = stem.casefold()
                changed = True
                break
    stem = re.sub(r"(?i)([-_](edit|edited|lr|final|修图|修圖))[-_ ]?\d+$", r"\1", stem)
    return stem.casefold()


def make_capture_key(
    *,
    filename: str,
    shot_at: str | None,
    camera_serial: str | None,
    camera_model: str | None,
    theme: str,
    relative_path: str,
    edited_suffixes: Iterable[str] = EDITED_DEFAULT_SUFFIXES,
) -> str:
    stem = normalized_stem(filename, edited_suffixes)
    identity = (camera_serial or camera_model or "unknown-camera").strip().casefold()
    if shot_at:
        raw = f"v1|{identity}|{shot_at}|{stem}"
    else:
        parent = str(Path(relative_path).parent).casefold()
        raw = f"v1-fallback|{theme.casefold()}|{parent}|{stem}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()
