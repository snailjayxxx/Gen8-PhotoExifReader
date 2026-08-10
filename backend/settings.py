from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_CONFIG = {
    "libraries": [],
    "raw_extensions": [".arw", ".cr2", ".cr3", ".nef", ".nrw", ".raf", ".orf", ".rw2", ".dng", ".pef", ".srw"],
    "image_extensions": [".jpg", ".jpeg", ".heic", ".heif", ".tif", ".tiff"],
    "edited_dir_keywords": ["修图", "修圖", "成片", "导出", "導出", "edited", "edit", "lightroom", "lr"],
    "jpeg_dir_keywords": ["jpg", "jpeg", "直出"],
    "raw_dir_keywords": ["raw", "原片"],
    "edited_filename_suffixes": ["-edit", "_edit", "-edited", "_edited", "-修图", "_修图", "-修圖", "_修圖", "-lr", "_lr", "-final", "_final"],
    "scan_batch_size": 64,
}


def data_dir() -> Path:
    root = os.environ.get("PHOTOEXIF_DATA_DIR")
    if root:
        return Path(root)
    return Path(__file__).resolve().parents[1] / "data"


def config_path() -> Path:
    return data_dir() / "config.json"


def load_config() -> dict[str, Any]:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        save_config(DEFAULT_CONFIG.copy())
        return DEFAULT_CONFIG.copy()
    with path.open("r", encoding="utf-8") as fh:
        current = json.load(fh)
    merged = DEFAULT_CONFIG.copy()
    merged.update(current)
    return merged


def save_config(config: dict[str, Any]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(config, fh, ensure_ascii=False, indent=2)
