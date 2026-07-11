from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from init_project import parse_markdown, parse_target  # noqa: E402
from utils import deep_merge, normalize_asset_path, parse_ratio  # noqa: E402


class MarkdownParserTests(unittest.TestCase):
    def test_parse_markdown_preserves_sections_lists_and_images(self) -> None:
        text = """# 标题

第一段说明。

- 条目一

![登录页面](images/login.png \"标题\")
"""
        sections = parse_markdown(text)
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0]["title"], "标题")
        types = [block["type"] for block in sections[0]["blocks"]]
        self.assertEqual(types, ["paragraph", "list_item", "image"])
        self.assertEqual(sections[0]["blocks"][-1]["target"], "images/login.png")

    def test_parse_target_supports_angle_brackets_and_url_encoding(self) -> None:
        self.assertEqual(parse_target("<images/a%20b.png>"), "images/a b.png")


class ConfigurationTests(unittest.TestCase):
    def test_deep_merge_keeps_unmodified_nested_values(self) -> None:
        base = {"video": {"fps": 30, "crf": 14}, "ratio": "16:9"}
        merged = deep_merge(base, {"video": {"crf": 18}})
        self.assertEqual(merged["video"], {"fps": 30, "crf": 18})
        self.assertEqual(merged["ratio"], "16:9")

    def test_parse_ratio_uses_registered_canvas(self) -> None:
        config = {
            "aspectRatio": "9:16",
            "canvas": {"9:16": {"width": 1080, "height": 1920, "dpr": 1}},
        }
        self.assertEqual(parse_ratio(config), (1080, 1920, 1.0))

    def test_asset_path_cannot_escape_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            with self.assertRaises(ValueError):
                normalize_asset_path(project, "../secret.txt")


class ProjectInitializationTests(unittest.TestCase):
    def test_init_project_copies_local_assets_and_creates_contract_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            input_dir = temp / "input"
            image_dir = input_dir / "images"
            image_dir.mkdir(parents=True)
            (image_dir / "screen.png").write_bytes(b"test-image")
            markdown = input_dir / "tutorial.md"
            markdown.write_text(
                "# 教程\n\n打开应用。\n\n![页面](images/screen.png)\n",
                encoding="utf-8",
            )
            project = temp / "project"

            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "init_project.py"),
                    "--input",
                    str(markdown),
                    "--project",
                    str(project),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            manifest = json.loads((project / "work" / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["assets"]), 1)
            self.assertEqual(manifest["missing_assets"], [])
            self.assertTrue((project / manifest["assets"][0]["path"]).exists())
            self.assertTrue((project / "work" / "fact-check.json").exists())
            self.assertTrue((project / "work" / "privacy-review.json").exists())


if __name__ == "__main__":
    unittest.main()
