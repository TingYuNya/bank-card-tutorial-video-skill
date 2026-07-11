from __future__ import annotations

import argparse
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from utils import ensure_project_dirs, ffprobe_json, load_config, load_json, parse_ratio, require_binary, run


def capture_filter(video: Path, filter_name: str) -> str:
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(video), "-af" if filter_name.startswith("silence") else "-vf", filter_name, "-f", "null", "-"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stderr


def make_contact_sheet(images: list[tuple[str, Path]], output: Path, cols: int = 4) -> None:
    if not images:
        return
    thumb_w, thumb_h = 360, 240
    label_h = 42
    rows = math.ceil(len(images) / cols)
    canvas = Image.new("RGB", (cols * thumb_w, rows * (thumb_h + label_h)), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for idx, (label, path) in enumerate(images):
        image = Image.open(path).convert("RGB")
        image.thumbnail((thumb_w - 16, thumb_h - 16))
        x = (idx % cols) * thumb_w
        y = (idx // cols) * (thumb_h + label_h)
        px = x + (thumb_w - image.width) // 2
        py = y + (thumb_h - image.height) // 2
        canvas.paste(image, (px, py))
        draw.text((x + 8, y + thumb_h + 10), label[:48], fill="black", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, quality=92)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect final video metadata and extract one key frame for every scene.")
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--video", type=Path)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()

    project = args.project.resolve()
    paths = ensure_project_dirs(project)
    config = load_config(project, args.config.resolve() if args.config else None)
    timeline = load_json(paths["work"] / "timeline.json")
    video = args.video.resolve() if args.video else paths["renders"] / "银行卡教程-final.mp4"
    if not video.exists():
        raise FileNotFoundError(video)
    require_binary("ffmpeg")
    require_binary("ffprobe")

    info = ffprobe_json(video)
    streams = info.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})
    width, height, dpr = parse_ratio(config)
    expected_w, expected_h = round(width * dpr), round(height * dpr)
    duration = float(info.get("format", {}).get("duration", 0))
    expected_duration = float(timeline.get("total_duration", 0))

    frames_dir = paths["quality"] / "frames"
    shutil.rmtree(frames_dir, ignore_errors=True)
    frames_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[tuple[str, Path]] = []
    for index, scene in enumerate(timeline.get("scenes", []), start=1):
        midpoint = (float(scene["start"]) + float(scene["end"])) / 2
        frame = frames_dir / f"{index:03d}-{scene['id']}.jpg"
        run(["ffmpeg", "-y", "-ss", f"{midpoint:.3f}", "-i", str(video), "-frames:v", "1", "-update", "1", "-q:v", "2", str(frame)])
        extracted.append((f"{scene['id']} @ {midpoint:.2f}s", frame))

    contact_sheet = paths["quality"] / "contact-sheet.jpg"
    make_contact_sheet(extracted, contact_sheet)

    black_log = capture_filter(video, "blackdetect=d=0.35:pix_th=0.98")
    silence_log = capture_filter(video, "silencedetect=noise=-50dB:d=1.0")
    black_events = re.findall(r"black_start:([0-9.]+).*?black_end:([0-9.]+).*?black_duration:([0-9.]+)", black_log)
    silence_events = re.findall(r"silence_start: ([0-9.]+)|silence_end: ([0-9.]+) \| silence_duration: ([0-9.]+)", silence_log)

    checks = [
        ("Video exists", True, str(video)),
        ("Resolution", video_stream.get("width") == expected_w and video_stream.get("height") == expected_h, f"actual {video_stream.get('width')}x{video_stream.get('height')}, expected {expected_w}x{expected_h}"),
        ("Video codec", bool(video_stream.get("codec_name")), str(video_stream.get("codec_name"))),
        ("Audio track", bool(audio_stream), str(audio_stream.get("codec_name") or "missing")),
        ("Duration", abs(duration - expected_duration) <= max(0.15, 1 / max(1, int(config.get('fps', 30)))), f"actual {duration:.3f}s, expected {expected_duration:.3f}s"),
        ("Scene key frames", len(extracted) == len(timeline.get("scenes", [])), f"{len(extracted)} / {len(timeline.get('scenes', []))}"),
        ("Long black frames", len(black_events) == 0, f"{len(black_events)} event(s)"),
    ]

    report_lines = [
        "# 最终视频验收报告",
        "",
        f"视频：`{video.relative_to(project).as_posix()}`",
        "",
        "## 自动检查",
        "",
        "| 检查项 | 状态 | 详情 |",
        "|---|---|---|",
    ]
    for label, ok, detail in checks:
        report_lines.append(f"| {label} | {'通过' if ok else '失败'} | {detail} |")

    report_lines.extend(["", "## 场景抽帧", "", f"已对 {len(extracted)} 个场景逐一抽取中间帧。总览：`quality/contact-sheet.jpg`。", ""])
    for label, path in extracted:
        report_lines.append(f"- `{path.relative_to(project).as_posix()}`，{label}")

    report_lines.extend(["", "## 黑帧与静音", ""])
    if black_events:
        for start, end, dur in black_events:
            report_lines.append(f"- 检测到黑帧：{start}s 至 {end}s，持续 {dur}s。")
    else:
        report_lines.append("- 未检测到持续 0.35 秒以上的黑帧。")
    report_lines.append(f"- FFmpeg 检测到 {len(silence_events)} 条静音起止日志。场景间的短停顿属于正常情况，超过 1 秒的静音需要人工复核。")

    report_lines.extend(
        [
            "",
            "## 人工复核清单",
            "",
            "- 打开 contact sheet，逐帧确认卡号、姓名、地址、账户号、验证码、二维码、余额和交易记录已经完整遮挡。",
            "- 对照时间线预览，确认图片裁切、标注、字幕位置和字号一致。",
            "- 试听英文按钮名、卡名、金额、日期和利率，确认没有错读。",
            "- 确认画面没有素材路径、内部审核信息、浏览器控件或调试 HUD。",
            "- 确认所有费用、资格和流程陈述仍与 fact-check.json 的来源一致。",
        ]
    )
    report = paths["quality"] / "quality-report.md"
    report.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    failed = [item for item in checks if not item[1]]
    print(f"[done] {report}")
    print(f"[frames] {contact_sheet}")
    if failed:
        for label, _, detail in failed:
            print(f"[failed] {label}: {detail}")
        return 1
    print("[ok] automatic checks passed; complete the manual privacy and visual review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
