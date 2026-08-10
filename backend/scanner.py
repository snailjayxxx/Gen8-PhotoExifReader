from __future__ import annotations

import json
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .capture_matcher import classify_role, make_capture_key, normalized_stem
from .db import Database
from .exiftool import read_metadata


def _chunks(items: list[Path], size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _float(value: Any) -> float | None:
    try:
        if value is None or value == "": return None
        return float(value)
    except (TypeError, ValueError): return None


def _int(value: Any) -> int | None:
    try:
        if value is None or value == "": return None
        return int(float(value))
    except (TypeError, ValueError): return None


def _shot_at(meta: dict[str, Any]) -> str | None:
    value = meta.get("DateTimeOriginal") or meta.get("CreateDate")
    if not value: return None
    text = str(value)
    if len(text) >= 19 and text[4] == ":" and text[7] == ":":
        return f"{text[0:4]}-{text[5:7]}-{text[8:10]}T{text[11:19]}"
    return text


def _exposure_seconds(meta: dict[str, Any]) -> float | None:
    value = meta.get("ExposureTime")
    numeric = _float(value)
    if numeric is not None: return numeric
    text = str(value or "")
    if "/" in text:
        try:
            a, b = text.split("/", 1)
            return float(a) / float(b)
        except (ValueError, ZeroDivisionError): pass
    return None


class Scanner:
    def __init__(self, db: Database, config: dict[str, Any]):
        self.db = db
        self.config = config
        self.raw_extensions = {x.casefold() for x in config["raw_extensions"]}
        self.allowed_extensions = self.raw_extensions | {x.casefold() for x in config["image_extensions"]}

    def run_all(self) -> dict[str, Any]:
        libraries = self.db.sync_libraries(self.config.get("libraries", []))
        result = {"libraries": [], "started_at": datetime.now().isoformat(timespec="seconds")}
        for lib in libraries:
            if lib["enabled"]:
                result["libraries"].append(self.run_library(dict(lib)))
        return result

    def run_library(self, library: dict[str, Any]) -> dict[str, Any]:
        root = Path(library["root_path"])
        with self.db.connect() as conn:
            cur = conn.execute("INSERT INTO scan_runs(library_id,status) VALUES(?, 'running')", (library["id"],))
            scan_id = int(cur.lastrowid)
        if not root.exists() or not root.is_dir():
            with self.db.connect() as conn:
                conn.execute("UPDATE scan_runs SET status='failed', finished_at=CURRENT_TIMESTAMP, message=? WHERE id=?", (f"Library not found: {root}", scan_id))
            return {"scan_id": scan_id, "status": "failed", "message": f"Library not found: {root}"}

        discovered: list[Path] = []
        for dirpath, _, filenames in os.walk(root):
            for name in filenames:
                path = Path(dirpath) / name
                if path.suffix.casefold() in self.allowed_extensions:
                    discovered.append(path)

        indexed = skipped = errors = 0
        changed: list[Path] = []
        with self.db.connect() as conn:
            for path in discovered:
                try: stat = path.stat()
                except OSError:
                    errors += 1; continue
                row = conn.execute("SELECT id,size_bytes,mtime FROM files WHERE absolute_path=?", (str(path),)).fetchone()
                if row and row["size_bytes"] == stat.st_size and math.isclose(row["mtime"], stat.st_mtime, abs_tol=0.0001):
                    conn.execute("UPDATE files SET active=1,last_seen_scan_id=? WHERE id=?", (scan_id, row["id"]))
                    skipped += 1
                else:
                    changed.append(path)

        batch_size = max(1, int(self.config.get("scan_batch_size", 64)))
        for batch in _chunks(changed, batch_size):
            try:
                metadata = read_metadata(batch)
                by_path = {str(item.get("SourceFile")): item for item in metadata}
            except Exception as exc:
                errors += len(batch)
                with self.db.connect() as conn:
                    conn.execute("UPDATE scan_runs SET message=? WHERE id=?", (str(exc)[:1000], scan_id))
                continue
            with self.db.connect() as conn:
                for path in batch:
                    try:
                        stat = path.stat()
                        meta = by_path.get(str(path), {})
                        relative = str(path.relative_to(root))
                        parts = Path(relative).parts
                        theme = parts[0] if len(parts) > 1 else "未分类"
                        role = classify_role(Path(relative), self.raw_extensions, self.config.get("edited_dir_keywords", []), self.config.get("jpeg_dir_keywords", []))
                        shot_at = _shot_at(meta)
                        camera_model = meta.get("Model")
                        camera_serial = meta.get("SerialNumber") or meta.get("InternalSerialNumber")
                        key = make_capture_key(
                            filename=path.name, shot_at=shot_at, camera_serial=str(camera_serial) if camera_serial else None,
                            camera_model=str(camera_model) if camera_model else None, theme=theme, relative_path=relative,
                            edited_suffixes=self.config.get("edited_filename_suffixes", []),
                        )
                        conn.execute(
                            """INSERT INTO captures(library_id,capture_key,theme,shot_at,camera_model,camera_serial,normalized_name)
                               VALUES(?,?,?,?,?,?,?) ON CONFLICT(library_id,capture_key) DO UPDATE SET
                               theme=COALESCE(excluded.theme,captures.theme), shot_at=COALESCE(excluded.shot_at,captures.shot_at),
                               camera_model=COALESCE(excluded.camera_model,captures.camera_model), camera_serial=COALESCE(excluded.camera_serial,captures.camera_serial)""",
                            (library["id"], key, theme, shot_at, camera_model, camera_serial, normalized_stem(path.name, self.config.get("edited_filename_suffixes", []))),
                        )
                        capture_id = conn.execute("SELECT id FROM captures WHERE library_id=? AND capture_key=?", (library["id"], key)).fetchone()[0]
                        keywords = meta.get("Keywords") or meta.get("Subject") or []
                        if not isinstance(keywords, list): keywords = [keywords]
                        values = (
                            library["id"], capture_id, str(path), relative, theme, path.name, path.suffix.casefold(), role, stat.st_size, stat.st_mtime, 1, scan_id,
                            shot_at, meta.get("Make"), camera_model, camera_serial, meta.get("LensModel") or meta.get("LensID"), _float(meta.get("FocalLength")),
                            _float(meta.get("FocalLengthIn35mmFormat")), _float(meta.get("FNumber")), str(meta.get("ExposureTime")) if meta.get("ExposureTime") is not None else None,
                            _exposure_seconds(meta), _int(meta.get("ISO")), _float(meta.get("ExposureCompensation")), _int(meta.get("ImageWidth")), _int(meta.get("ImageHeight")),
                            str(meta.get("Orientation")) if meta.get("Orientation") is not None else None, _float(meta.get("GPSLatitude")), _float(meta.get("GPSLongitude")),
                            _int(meta.get("Rating")), json.dumps(keywords, ensure_ascii=False), json.dumps(meta, ensure_ascii=False),
                        )
                        conn.execute(
                            """INSERT INTO files(library_id,capture_id,absolute_path,relative_path,theme,filename,extension,role,size_bytes,mtime,active,last_seen_scan_id,
                            shot_at,make,camera_model,camera_serial,lens_model,focal_length,focal_35mm,aperture,exposure_time,exposure_seconds,iso,exposure_comp,width,height,
                            orientation,gps_lat,gps_lon,rating,keywords_json,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                            ON CONFLICT(absolute_path) DO UPDATE SET library_id=excluded.library_id,capture_id=excluded.capture_id,relative_path=excluded.relative_path,
                            theme=excluded.theme,filename=excluded.filename,extension=excluded.extension,role=excluded.role,size_bytes=excluded.size_bytes,mtime=excluded.mtime,
                            active=1,last_seen_scan_id=excluded.last_seen_scan_id,shot_at=excluded.shot_at,make=excluded.make,camera_model=excluded.camera_model,
                            camera_serial=excluded.camera_serial,lens_model=excluded.lens_model,focal_length=excluded.focal_length,focal_35mm=excluded.focal_35mm,
                            aperture=excluded.aperture,exposure_time=excluded.exposure_time,exposure_seconds=excluded.exposure_seconds,iso=excluded.iso,
                            exposure_comp=excluded.exposure_comp,width=excluded.width,height=excluded.height,orientation=excluded.orientation,gps_lat=excluded.gps_lat,
                            gps_lon=excluded.gps_lon,rating=excluded.rating,keywords_json=excluded.keywords_json,metadata_json=excluded.metadata_json,indexed_at=CURRENT_TIMESTAMP""",
                            values,
                        )
                        indexed += 1
                    except Exception:
                        errors += 1

        with self.db.connect() as conn:
            conn.execute("UPDATE files SET active=0 WHERE library_id=? AND COALESCE(last_seen_scan_id,-1) != ?", (library["id"], scan_id))
            conn.execute("UPDATE scan_runs SET status='finished',finished_at=CURRENT_TIMESTAMP,discovered=?,indexed=?,skipped=?,errors=? WHERE id=?", (len(discovered), indexed, skipped, errors, scan_id))
            conn.execute("DELETE FROM captures WHERE library_id=? AND NOT EXISTS (SELECT 1 FROM files WHERE files.capture_id=captures.id AND files.active=1)", (library["id"],))
        return {"scan_id": scan_id, "status": "finished", "discovered": len(discovered), "indexed": indexed, "skipped": skipped, "errors": errors}
