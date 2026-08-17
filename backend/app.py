from __future__ import annotations

import argparse
import json
import mimetypes
import platform
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .db import Database
from .exiftool import probe_exiftool
from .scanner import Scanner
from .settings import data_dir, load_config, save_config

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
APP_VERSION = "0.1.1-0005"
DB = Database(data_dir() / "photoexif.sqlite3")
SCAN_LOCK = threading.Lock()
SCAN_STATE = {"running": False, "last_result": None, "error": None}


def _scan_worker() -> None:
    if not SCAN_LOCK.acquire(blocking=False):
        return
    SCAN_STATE.update({"running": True, "error": None})
    try:
        SCAN_STATE["last_result"] = Scanner(DB, load_config()).run_all()
    except Exception as exc:
        SCAN_STATE["error"] = str(exc)
    finally:
        SCAN_STATE["running"] = False
        SCAN_LOCK.release()


def _runtime_status() -> dict:
    payload = {
        "version": APP_VERSION,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "exiftool": {"ok": False, "message": "unknown"},
    }
    try:
        info = probe_exiftool()
        payload["exiftool"] = {"ok": True, **info}
    except Exception as exc:
        payload["exiftool"] = {"ok": False, "message": str(exc)}
    return payload


class Handler(BaseHTTPRequestHandler):
    server_version = f"Gen8PhotoExifReader/{APP_VERSION}"

    def log_message(self, fmt: str, *args):
        print(f"[http] {self.address_string()} - {fmt % args}")

    def _json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length).decode("utf-8") or "{}")

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            return self._json({"ok": True, "version": APP_VERSION, "mode": "python"})
        if parsed.path == "/api/runtime":
            return self._json(_runtime_status())
        if parsed.path == "/api/dashboard":
            return self._json(DB.dashboard())
        if parsed.path == "/api/settings":
            return self._json(load_config())
        if parsed.path == "/api/scan/status":
            return self._json(SCAN_STATE)
        if parsed.path == "/api/photos":
            q = parse_qs(parsed.query)
            try:
                limit = min(max(int(q.get("limit", [100])[0]), 1), 500)
                offset = max(int(q.get("offset", [0])[0]), 0)
            except ValueError:
                return self._json({"error": "invalid pagination"}, HTTPStatus.BAD_REQUEST)
            rows = DB.photos(
                limit=limit,
                offset=offset,
                theme=q.get("theme", [None])[0],
                role=q.get("role", [None])[0],
            )
            return self._json({"items": rows, "limit": limit, "offset": offset})
        return self._static(parsed.path)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/settings":
            try:
                config = self._read_json()
                if not isinstance(config.get("libraries", []), list):
                    raise ValueError("libraries must be a list")
                save_config(config)
                DB.sync_libraries(config.get("libraries", []))
                return self._json({"ok": True, "config": load_config()})
            except Exception as exc:
                return self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        if parsed.path == "/api/scan":
            if SCAN_STATE["running"]:
                return self._json({"ok": False, "message": "scan already running"}, HTTPStatus.CONFLICT)
            threading.Thread(target=_scan_worker, daemon=True).start()
            return self._json({"ok": True, "message": "scan started"}, HTTPStatus.ACCEPTED)
        return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def _static(self, request_path: str):
        relative = "index.html" if request_path in ("", "/") else request_path.lstrip("/")
        target = (FRONTEND / relative).resolve()
        if FRONTEND.resolve() not in target.parents and target != FRONTEND.resolve():
            return self._json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
        if not target.is_file():
            target = FRONTEND / "index.html"
        body = target.read_bytes()
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header(
            "Content-Type",
            content_type + ("; charset=utf-8" if content_type.startswith("text/") or content_type == "application/javascript" else ""),
        )
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Gen8 Photo EXIF Reader")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=9865, type=int)
    args = parser.parse_args()
    print(f"Gen8 Photo EXIF Reader {APP_VERSION} listening on http://{args.host}:{args.port}")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
