from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import sys
from pathlib import Path

from utils import SKILL_DIR, load_environment


def status(ok: bool, label: str, detail: str = "") -> None:
    mark = "OK" if ok else "MISSING"
    suffix = f" ({detail})" if detail else ""
    print(f"[{mark}] {label}{suffix}")


def main() -> int:
    load_environment()
    print(f"Skill: {SKILL_DIR}")
    print(f"Python: {sys.version.split()[0]} on {platform.platform()}")

    status(sys.version_info >= (3, 11), "Python 3.11+")
    for binary in ["ffmpeg", "ffprobe"]:
        status(bool(shutil.which(binary)), binary, shutil.which(binary) or "")

    packages = {
        "openai": "OpenAI TTS and alignment",
        "requests": "ElevenLabs HTTP client",
        "dotenv": "environment loading",
        "PIL": "contact sheet generation",
        "playwright": "deterministic frame rendering",
        "azure.cognitiveservices.speech": "Azure Speech",
    }
    for module, label in packages.items():
        try:
            available = importlib.util.find_spec(module) is not None
        except (ImportError, ModuleNotFoundError):
            available = False
        status(available, label)

    providers = {
        "ElevenLabs": bool(os.getenv("ELEVENLABS_API_KEY") and os.getenv("ELEVENLABS_VOICE_ID")),
        "OpenAI": bool(os.getenv("OPENAI_API_KEY")),
        "Azure Speech": bool(os.getenv("SPEECH_KEY") and os.getenv("SPEECH_REGION")),
    }
    for name, ok in providers.items():
        status(ok, f"{name} credentials")

    print("\nAt least one TTS provider is required. Run `python -m playwright install chromium` after installing requirements.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
