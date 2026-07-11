from __future__ import annotations

import argparse
import hashlib
import re
import shutil
from pathlib import Path
from urllib.parse import unquote

from utils import ensure_project_dirs, safe_rel, save_json

IMAGE_RE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<target>[^)]+)\)")
HEADING_RE = re.compile(r"^(?P<level>#{1,6})\s+(?P<title>.+?)\s*$")
LIST_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)(?P<text>.+)$")


def parse_target(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("<") and ">" in raw:
        return unquote(raw[1 : raw.index(">")])
    # Markdown allows an optional quoted title after the path.
    match = re.match(r'^(.*?)(?:\s+["\'].*["\'])?$', raw)
    return unquote((match.group(1) if match else raw).strip())


def slug(prefix: str, index: int) -> str:
    return f"{prefix}-{index:03d}"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_markdown(text: str) -> list[dict]:
    sections: list[dict] = []
    current: dict | None = None
    paragraph: list[str] = []

    def ensure_current() -> dict:
        nonlocal current
        if current is None:
            current = {
                "id": slug("section", len(sections) + 1),
                "level": 1,
                "title": "正文",
                "blocks": [],
            }
            sections.append(current)
        return current

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            content = " ".join(line.strip() for line in paragraph if line.strip()).strip()
            if content:
                ensure_current()["blocks"].append({"type": "paragraph", "text": content})
        paragraph = []

    for line_no, line in enumerate(text.splitlines(), start=1):
        heading = HEADING_RE.match(line)
        if heading:
            flush_paragraph()
            current = {
                "id": slug("section", len(sections) + 1),
                "level": len(heading.group("level")),
                "title": heading.group("title").strip(),
                "line": line_no,
                "blocks": [],
            }
            sections.append(current)
            continue

        images = list(IMAGE_RE.finditer(line))
        if images:
            flush_paragraph()
            cursor = 0
            for match in images:
                before = line[cursor : match.start()].strip()
                if before:
                    ensure_current()["blocks"].append({"type": "paragraph", "text": before, "line": line_no})
                ensure_current()["blocks"].append(
                    {
                        "type": "image",
                        "alt": match.group("alt").strip(),
                        "target": parse_target(match.group("target")),
                        "line": line_no,
                    }
                )
                cursor = match.end()
            after = line[cursor:].strip()
            if after:
                ensure_current()["blocks"].append({"type": "paragraph", "text": after, "line": line_no})
            continue

        item = LIST_RE.match(line)
        if item:
            flush_paragraph()
            ensure_current()["blocks"].append({"type": "list_item", "text": item.group("text").strip(), "line": line_no})
            continue

        if line.strip().startswith("```"):
            flush_paragraph()
            ensure_current()["blocks"].append({"type": "code_fence", "text": line.strip(), "line": line_no})
            continue

        if not line.strip():
            flush_paragraph()
            continue

        paragraph.append(line)

    flush_paragraph()
    return sections


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize a bank-card tutorial video project from Markdown.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    input_md = args.input.resolve()
    project = args.project.resolve()
    if not input_md.exists():
        raise FileNotFoundError(input_md)
    if project.exists() and any(project.iterdir()) and not args.overwrite:
        raise RuntimeError(f"Project directory is not empty: {project}. Use --overwrite to reuse it.")

    paths = ensure_project_dirs(project)
    original_text = input_md.read_text(encoding="utf-8")
    sections = parse_markdown(original_text)

    source_md = paths["source"] / "tutorial.original.md"
    source_md.write_text(original_text, encoding="utf-8")

    assets: list[dict] = []
    missing: list[dict] = []
    copied_by_source: dict[Path, str] = {}
    asset_counter = 0

    for section in sections:
        for block in section["blocks"]:
            if block["type"] != "image":
                continue
            target = block["target"]
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", target):
                missing.append({"target": target, "reason": "remote image is not downloaded", "line": block.get("line")})
                block["status"] = "remote"
                continue

            source_path = (input_md.parent / target).resolve()
            if not source_path.exists() or not source_path.is_file():
                missing.append({"target": target, "reason": "file not found", "line": block.get("line")})
                block["status"] = "missing"
                continue

            asset_counter += 1
            if source_path in copied_by_source:
                rel = copied_by_source[source_path]
            else:
                ext = source_path.suffix.lower() or ".bin"
                safe_name = re.sub(r"[^0-9A-Za-z._-]+", "-", source_path.stem).strip("-") or "asset"
                dest = paths["assets"] / f"{asset_counter:03d}-{safe_name}{ext}"
                shutil.copy2(source_path, dest)
                rel = safe_rel(dest, project)
                copied_by_source[source_path] = rel
                assets.append(
                    {
                        "id": slug("asset", len(assets) + 1),
                        "path": rel,
                        "original": str(source_path),
                        "alt": block.get("alt", ""),
                        "sha256": sha256(dest),
                        "bytes": dest.stat().st_size,
                    }
                )
            block["asset"] = rel
            block["status"] = "copied"

    manifest = {
        "version": 1,
        "input": str(input_md),
        "source_markdown": safe_rel(source_md, project),
        "sections": len(sections),
        "assets": assets,
        "missing_assets": missing,
    }
    save_json(paths["work"] / "sections.json", {"version": 1, "sections": sections})
    save_json(paths["work"] / "manifest.json", manifest)

    save_json(
        paths["work"] / "fact-check.json",
        {
            "version": 1,
            "product": {"bank": "", "card": "", "region": "", "channel": ""},
            "claims": [],
            "summary": {"verified": 0, "qualified": 0, "removed": 0, "unresolved": 0},
        },
    )
    save_json(
        paths["work"] / "privacy-review.json",
        {
            "version": 1,
            "assets": [
                {
                    "asset": item["path"],
                    "reviewed": False,
                    "contains_sensitive_data": None,
                    "notes": "",
                    "redactions": [],
                }
                for item in assets
            ],
        },
    )
    save_json(
        paths["work"] / "narration.json",
        {"title": "", "language": "zh-CN", "scenes": []},
    )
    save_json(paths["work"] / "storyboard.json", {"version": 1, "scenes": []})
    (paths["work"] / "revised-article.md").write_text("# 待 Agent 完成\n", encoding="utf-8")
    (paths["work"] / "on-screen-text.md").write_text("# 待 Agent 完成\n", encoding="utf-8")
    (paths["sources"] / "source-list.md").write_text("# 官方来源清单\n", encoding="utf-8")

    print(f"[done] project initialized: {project}")
    print(f"[info] sections: {len(sections)}")
    print(f"[info] copied assets: {len(assets)}")
    if missing:
        print(f"[warning] missing or remote assets: {len(missing)}")
        for item in missing:
            print(f"  line {item.get('line')}: {item['target']} ({item['reason']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
