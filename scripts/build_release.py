from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {".git", "__pycache__", "output", "log", "memory", "dist"}
EXCLUDED_NAMES = {".env", "PACKAGE-MANIFEST.json"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".zip", ".tar", ".gz", ".mp4", ".mov", ".m4a", ".mp3", ".wav"}


def included_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in EXCLUDED_DIRS for part in rel.parts):
            continue
        if path.name in EXCLUDED_NAMES or path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(root: Path, files: list[Path]) -> dict:
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    return {
        "name": "bank-card-tutorial-video-skill",
        "version": version,
        "generated_at": datetime.now(timezone.utc).date().isoformat(),
        "files": [
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in files
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the public release archive and file manifest.")
    parser.add_argument("--root", type=Path, default=SKILL_DIR)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    output = (args.output or root.parent / f"bank-card-tutorial-video-skill-v{version}.zip").resolve()

    files = included_files(root)
    manifest = build_manifest(root, files)
    manifest_path = root / "PACKAGE-MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    archive_files = included_files(root) + [manifest_path]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(archive_files, key=lambda item: item.relative_to(root).as_posix()):
            archive.write(path, path.relative_to(root).as_posix())

    checksum = sha256(output)
    checksum_path = output.with_suffix(output.suffix + ".sha256")
    checksum_path.write_text(f"{checksum}  {output.name}\n", encoding="utf-8")

    print(f"[done] files: {len(archive_files)}")
    print(f"[done] archive: {output}")
    print(f"[done] sha256: {checksum}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
