from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


SKILL_DIR = Path(__file__).resolve().parents[1]


def load_environment(project_dir: Path | None = None) -> None:
    if load_dotenv is None:
        return
    load_dotenv(SKILL_DIR / ".env", override=False)
    if project_dir is not None:
        load_dotenv(project_dir / ".env", override=False)


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(project_dir: Path | None = None, explicit: Path | None = None) -> dict[str, Any]:
    config = load_json(SKILL_DIR / "config" / "default.json")
    if project_dir is not None:
        for candidate in [project_dir / "project.json", project_dir / "config.json"]:
            if candidate.exists():
                config = deep_merge(config, load_json(candidate))
    if explicit is not None:
        config = deep_merge(config, load_json(explicit))
    return config


def require_binary(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"Required binary not found in PATH: {name}")
    return path


def run(cmd: list[str], *, cwd: Path | None = None, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        text=True,
        capture_output=capture,
    )


def ffprobe_duration(path: Path) -> float:
    require_binary("ffprobe")
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture=True,
    )
    return float(result.stdout.strip())


def ffprobe_json(path: Path) -> dict[str, Any]:
    require_binary("ffprobe")
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
            "-of",
            "json",
            str(path),
        ],
        capture=True,
    )
    return json.loads(result.stdout)


def project_paths(project_dir: Path) -> dict[str, Path]:
    return {
        "project": project_dir,
        "source": project_dir / "source",
        "assets": project_dir / "source" / "assets",
        "work": project_dir / "work",
        "audio": project_dir / "audio",
        "audio_scenes": project_dir / "audio" / "scenes",
        "subtitles": project_dir / "subtitles",
        "review": project_dir / "review",
        "renders": project_dir / "renders",
        "quality": project_dir / "quality",
        "sources": project_dir / "sources",
    }


def ensure_project_dirs(project_dir: Path) -> dict[str, Path]:
    paths = project_paths(project_dir)
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def safe_rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def parse_ratio(config: dict[str, Any]) -> tuple[int, int, float]:
    ratio = config.get("aspectRatio", "16:9")
    canvas = config.get("canvas", {}).get(ratio)
    if not canvas:
        raise ValueError(f"Unsupported aspectRatio: {ratio}")
    return int(canvas["width"]), int(canvas["height"]), float(canvas.get("dpr", 1.0))


def normalize_asset_path(project_dir: Path, value: str) -> Path:
    candidate = (project_dir / value).resolve()
    if project_dir.resolve() not in candidate.parents and candidate != project_dir.resolve():
        raise ValueError(f"Asset escapes project directory: {value}")
    return candidate
