from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from utils import SKILL_DIR, ensure_project_dirs


def main() -> int:
    parser = argparse.ArgumentParser(description="Copy review and final-player templates into a project.")
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    project = args.project.resolve()
    paths = ensure_project_dirs(project)
    copies = [
        (SKILL_DIR / "templates" / "storyboard-audit.html", paths["review"] / "storyboard-audit.html"),
        (SKILL_DIR / "templates" / "timeline-preview.html", paths["review"] / "timeline-preview.html"),
        (SKILL_DIR / "templates" / "final-player.html", paths["renders"] / "final-player.html"),
    ]
    for source, dest in copies:
        if dest.exists() and not args.overwrite:
            print(f"[keep] {dest}")
            continue
        shutil.copy2(source, dest)
        print(f"[copy] {dest}")
    print("[done] review pages prepared")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
