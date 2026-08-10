from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS libraries (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, root_path TEXT NOT NULL UNIQUE, enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS captures (
    id INTEGER PRIMARY KEY, library_id INTEGER NOT NULL, capture_key TEXT NOT NULL, theme TEXT, shot_at TEXT,
    camera_model TEXT, camera_serial TEXT, normalized_name TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(library_id, capture_key), FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY, library_id INTEGER NOT NULL, capture_id INTEGER, absolute_path TEXT NOT NULL UNIQUE,
    relative_path TEXT NOT NULL, theme TEXT, filename TEXT NOT NULL, extension TEXT, role TEXT NOT NULL,
    size_bytes INTEGER NOT NULL, mtime REAL NOT NULL, active INTEGER NOT NULL DEFAULT 1, last_seen_scan_id INTEGER,
    shot_at TEXT, make TEXT, camera_model TEXT, camera_serial TEXT, lens_model TEXT, focal_length REAL, focal_35mm REAL,
    aperture REAL, exposure_time TEXT, exposure_seconds REAL, iso INTEGER, exposure_comp REAL, width INTEGER, height INTEGER,
    orientation TEXT, gps_lat REAL, gps_lon REAL, rating INTEGER, keywords_json TEXT, metadata_json TEXT,
    indexed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE CASCADE,
    FOREIGN KEY(capture_id) REFERENCES captures(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_files_active ON files(active);
CREATE INDEX IF NOT EXISTS idx_files_theme ON files(theme);
CREATE INDEX IF NOT EXISTS idx_files_role ON files(role);
CREATE INDEX IF NOT EXISTS idx_files_camera ON files(camera_model);
CREATE INDEX IF NOT EXISTS idx_files_lens ON files(lens_model);
CREATE INDEX IF NOT EXISTS idx_files_capture ON files(capture_id);
CREATE INDEX IF NOT EXISTS idx_captures_theme ON captures(theme);
CREATE TABLE IF NOT EXISTS scan_runs (
    id INTEGER PRIMARY KEY, library_id INTEGER, status TEXT NOT NULL, started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT, discovered INTEGER NOT NULL DEFAULT 0, indexed INTEGER NOT NULL DEFAULT 0,
    skipped INTEGER NOT NULL DEFAULT 0, errors INTEGER NOT NULL DEFAULT 0, message TEXT,
    FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE SET NULL
);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def sync_libraries(self, libraries: list[dict[str, Any]]) -> list[sqlite3.Row]:
        with self.connect() as conn:
            for item in libraries:
                root = str(Path(item["path"]).expanduser())
                name = item.get("name") or Path(root).name or root
                enabled = 1 if item.get("enabled", True) else 0
                conn.execute(
                    """INSERT INTO libraries(name, root_path, enabled) VALUES(?,?,?)
                       ON CONFLICT(root_path) DO UPDATE SET name=excluded.name, enabled=excluded.enabled""",
                    (name, root, enabled),
                )
            return conn.execute("SELECT * FROM libraries ORDER BY id").fetchall()

    def dashboard(self) -> dict[str, Any]:
        with self.connect() as conn:
            one = lambda sql, args=(): conn.execute(sql, args).fetchone()[0]
            def grouped(field: str, table: str = "files", where: str = "active=1", limit: int = 12):
                sql = f"SELECT {field} AS label, COUNT(*) AS count FROM {table} WHERE {where} AND {field} IS NOT NULL AND {field} != '' GROUP BY {field} ORDER BY count DESC LIMIT ?"
                return [dict(row) for row in conn.execute(sql, (limit,)).fetchall()]
            return {
                "capture_count": one("SELECT COUNT(*) FROM captures c WHERE EXISTS (SELECT 1 FROM files f WHERE f.capture_id=c.id AND f.active=1)"),
                "file_count": one("SELECT COUNT(*) FROM files WHERE active=1"),
                "raw_count": one("SELECT COUNT(*) FROM files WHERE active=1 AND role='raw'"),
                "edited_count": one("SELECT COUNT(DISTINCT capture_id) FROM files WHERE active=1 AND role='edited' AND capture_id IS NOT NULL"),
                "themes": grouped("theme", "captures", "EXISTS (SELECT 1 FROM files f WHERE f.capture_id=captures.id AND f.active=1)"),
                "cameras": grouped("camera_model"),
                "lenses": grouped("lens_model"),
                "roles": grouped("role", limit=10),
                "apertures": [dict(r) for r in conn.execute("SELECT ROUND(aperture,1) AS label, COUNT(*) AS count FROM files WHERE active=1 AND role='raw' AND aperture IS NOT NULL GROUP BY ROUND(aperture,1) ORDER BY count DESC LIMIT 16")],
                "iso": [dict(r) for r in conn.execute("SELECT iso AS label, COUNT(*) AS count FROM files WHERE active=1 AND role='raw' AND iso IS NOT NULL GROUP BY iso ORDER BY count DESC LIMIT 16")],
                "focal_lengths": [dict(r) for r in conn.execute("""
                    SELECT CASE
                        WHEN focal_length < 16 THEN '<16mm' WHEN focal_length < 24 THEN '16–23mm'
                        WHEN focal_length < 35 THEN '24–34mm' WHEN focal_length < 50 THEN '35–49mm'
                        WHEN focal_length < 70 THEN '50–69mm' WHEN focal_length < 100 THEN '70–99mm'
                        WHEN focal_length < 200 THEN '100–199mm' WHEN focal_length < 400 THEN '200–399mm'
                        ELSE '≥400mm' END AS label, COUNT(*) AS count
                    FROM files WHERE active=1 AND role='raw' AND focal_length IS NOT NULL
                    GROUP BY label ORDER BY count DESC
                """)],
                "shutters": [dict(r) for r in conn.execute("""
                    SELECT CASE
                        WHEN exposure_seconds <= 0.00025 THEN '≤1/4000' WHEN exposure_seconds <= 0.0005 THEN '1/2000'
                        WHEN exposure_seconds <= 0.001 THEN '1/1000' WHEN exposure_seconds <= 0.002 THEN '1/500'
                        WHEN exposure_seconds <= 0.004 THEN '1/250' WHEN exposure_seconds <= 0.008 THEN '1/125'
                        WHEN exposure_seconds <= 0.0167 THEN '1/60' WHEN exposure_seconds <= 0.0334 THEN '1/30'
                        WHEN exposure_seconds <= 0.0667 THEN '1/15' WHEN exposure_seconds <= 0.125 THEN '1/8'
                        WHEN exposure_seconds <= 0.25 THEN '1/4' WHEN exposure_seconds <= 0.5 THEN '1/2'
                        WHEN exposure_seconds <= 1 THEN '1s' WHEN exposure_seconds <= 2 THEN '2s'
                        WHEN exposure_seconds <= 4 THEN '4s' ELSE '>4s' END AS label, COUNT(*) AS count
                    FROM files WHERE active=1 AND role='raw' AND exposure_seconds IS NOT NULL
                    GROUP BY label ORDER BY count DESC
                """)],
            }

    def photos(self, limit: int = 100, offset: int = 0, theme: str | None = None, role: str | None = None) -> list[dict[str, Any]]:
        where = ["active=1"]
        args: list[Any] = []
        if theme:
            where.append("theme=?")
            args.append(theme)
        if role:
            where.append("role=?")
            args.append(role)
        args.extend([limit, offset])
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT id,capture_id,relative_path,theme,filename,role,shot_at,camera_model,lens_model,focal_length,aperture,exposure_time,iso FROM files WHERE {' AND '.join(where)} ORDER BY COALESCE(shot_at,'' ) DESC, id DESC LIMIT ? OFFSET ?",
                args,
            ).fetchall()
            return [dict(r) for r in rows]
