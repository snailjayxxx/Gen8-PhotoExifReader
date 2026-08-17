#!/usr/bin/env python3
"""Build the DSM 6.1+ x86_64 SPK using strict USTAR archives.

The package includes a statically linked native diagnostic HTTP server. If the
Python backend cannot start on an older DSM installation, the package still
stays in Running state and exposes the startup reason on port 9865.
"""
from __future__ import annotations

import argparse
import gzip
import io
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def add_ustar(tf: tarfile.TarFile, path: Path, arcname: str) -> None:
    info = tf.gettarinfo(str(path), arcname=arcname)
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
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


def copy_tree(source: Path, destination: Path) -> None:
    if source.exists():
        shutil.copytree(source, destination, dirs_exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(ROOT / "dist" / "Gen8-PhotoExifReader-0.1.1-0003-DSM6.1-x86_64.spk"))
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="photoexif-spk-") as tmp:
        work = Path(tmp)
        payload = work / "payload"
        root = work / "spk"
        payload.mkdir()
        root.mkdir()

        copy_tree(ROOT / "backend", payload / "backend")
        copy_tree(ROOT / "frontend", payload / "frontend")
        copy_tree(ROOT / "runtime", payload / "runtime")
        copy_tree(ROOT / "vendor", payload / "vendor")

        native = payload / "native"
        native.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            "gcc", "-O2", "-static", "-s",
            str(ROOT / "spk" / "native" / "diag_server.c"),
            "-o", str(native / "diag-server"),
        ], check=True)
        (native / "diag-server").chmod(0o755)

        shutil.copy2(ROOT / "spk" / "INFO", root / "INFO")
        shutil.copytree(ROOT / "spk" / "scripts", root / "scripts")
        shutil.copytree(ROOT / "spk" / "conf", root / "conf")
        for icon in ("PACKAGE_ICON.PNG", "PACKAGE_ICON_256.PNG"):
            source = ROOT / "spk" / icon
            if source.exists():
                shutil.copy2(source, root / icon)

        write_package_tgz(payload, root / "package.tgz")

        order = ["INFO", "PACKAGE_ICON.PNG", "PACKAGE_ICON_256.PNG", "package.tgz", "scripts", "conf"]
        with tarfile.open(output, "w", format=tarfile.USTAR_FORMAT) as tf:
            for name in order:
                path = root / name
                if not path.exists():
                    continue
                entries = [path] + sorted(path.rglob("*")) if path.is_dir() else [path]
                for entry in entries:
                    add_ustar(tf, entry, str(entry.relative_to(root)))

    print(output)


if __name__ == "__main__":
    main()
