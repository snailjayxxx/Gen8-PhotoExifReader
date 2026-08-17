#!/usr/bin/env python3
"""Build a DSM 6.1-compatible SPK using strict USTAR archives.

The script intentionally avoids GNU/PAX tar extensions so older DSM 6.x
Package Center versions can parse the archive more reliably.
"""
from __future__ import annotations

import argparse
import gzip
import io
import os
import shutil
import stat
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def add_ustar(tf: tarfile.TarFile, path: Path, arcname: str) -> None:
    info = tf.gettarinfo(str(path), arcname=arcname)
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    info.mtime = 0
    if path.is_file():
        with path.open("rb") as handle:
            tf.addfile(info, handle)
    else:
        tf.addfile(info)


def write_package_tgz(source: Path, destination: Path) -> None:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as tf:
        for path in sorted(source.rglob("*")):
            add_ustar(tf, path, str(path.relative_to(source)))
    with destination.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as gz:
            gz.write(buffer.getvalue())


def copy_tree_files(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    for path in source.rglob("*"):
        target = destination / path.relative_to(source)
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(ROOT / "dist" / "Gen8-PhotoExifReader-0.1.1-0002-DSM6.1-noarch.spk"))
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="photoexif-spk-") as tmp:
        work = Path(tmp)
        payload = work / "payload"
        root = work / "spk"
        payload.mkdir()
        root.mkdir()

        # Runtime payload.
        copy_tree_files(ROOT / "backend", payload / "backend")
        copy_tree_files(ROOT / "frontend", payload / "frontend")
        copy_tree_files(ROOT / "runtime", payload / "runtime")
        copy_tree_files(ROOT / "vendor", payload / "vendor")

        shutil.copy2(ROOT / "spk" / "INFO", root / "INFO")
        shutil.copytree(ROOT / "spk" / "scripts", root / "scripts")
        if (ROOT / "spk" / "conf").exists():
            shutil.copytree(ROOT / "spk" / "conf", root / "conf")
        else:
            (root / "conf").mkdir()
            (root / "conf" / "privilege").write_text('{\n  "defaults": {\n    "run-as": "package"\n  }\n}\n', encoding="utf-8")

        for icon in ("PACKAGE_ICON.PNG", "PACKAGE_ICON_256.PNG"):
            source = ROOT / "spk" / icon
            if source.exists():
                shutil.copy2(source, root / icon)

        write_package_tgz(payload, root / "package.tgz")

        order = ["INFO", "package.tgz", "scripts", "conf", "PACKAGE_ICON.PNG", "PACKAGE_ICON_256.PNG"]
        with tarfile.open(output, "w", format=tarfile.USTAR_FORMAT) as tf:
            for name in order:
                path = root / name
                if not path.exists():
                    continue
                paths = [path] + sorted(path.rglob("*")) if path.is_dir() else [path]
                for entry in paths:
                    add_ustar(tf, entry, str(entry.relative_to(root)))

    print(output)


if __name__ == "__main__":
    main()
