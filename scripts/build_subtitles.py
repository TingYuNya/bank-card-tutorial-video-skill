from __future__ import annotations

import argparse
import math
import re
from pathlib import Path
from typing import Any

from utils import ensure_project_dirs, load_config, load_json, parse_ratio, save_json

PUNCTUATION = "。！？；：，、,.!?;:"


def weighted_length(text: str) -> float:
    total = 0.0
    for char in text:
        if char.isspace():
            total += 0.25
        elif ord(char) < 128:
            total += 0.55
        else:
            total += 1.0
    return total


def display_tokens(text: str) -> list[str]:
    """Tokenize without breaking Latin words, card names, model names, or numbers."""
    return re.findall(r"[A-Za-z0-9]+(?:[._/+%:-][A-Za-z0-9]+)*|\s+|.", text, flags=re.S)


def layout_lines(text: str, limit: float) -> list[str]:
    lines: list[str] = []
    current = ""
    for token in display_tokens(text):
        if token.isspace():
            if current and not current.endswith(" "):
                current += " "
            continue
        candidate = current + token
        if current.strip() and weighted_length(candidate.rstrip()) > limit:
            lines.append(current.strip())
            current = token
        else:
            current = candidate

        # An unusually long unbroken token may still exceed the line. Split it only as a last resort.
        if weighted_length(current.strip()) > limit and not lines:
            chunk = ""
            remainder = ""
            for char in current.strip():
                if chunk and weighted_length(chunk + char) > limit:
                    remainder += char
                elif remainder:
                    remainder += char
                else:
                    chunk += char
            if chunk and remainder:
                lines.append(chunk)
                current = remainder
    if current.strip():
        lines.append(current.strip())
    return lines


def wrap_lines(text: str, max_chars: int, max_lines: int) -> str:
    text = text.strip()
    if not text:
        return ""

    initial_limit = float(max_chars)
    lines = layout_lines(text, initial_limit)
    if len(lines) <= max_lines:
        return "\n".join(lines)

    # Increase the target width only as much as needed to stay within max_lines.
    low = initial_limit
    high = max(initial_limit, weighted_length(text))
    best = lines
    for _ in range(24):
        mid = (low + high) / 2
        candidate = layout_lines(text, mid)
        if len(candidate) <= max_lines:
            best = candidate
            high = mid
        else:
            low = mid
    return "\n".join(best[:max_lines])


def split_text(text: str, max_chars: int, max_lines: int) -> list[tuple[int, int, str]]:
    text = text.strip()
    if not text:
        return []
    capacity = max_chars * max_lines
    pieces: list[tuple[int, int, str]] = []
    start = 0
    cursor = 0
    buffer_start = 0

    while cursor < len(text):
        char = text[cursor]
        current = text[buffer_start : cursor + 1]
        should_split = char in "。！？；" or (char in "，：" and weighted_length(current) >= max_chars * 0.8)
        too_long = weighted_length(current) >= capacity
        if should_split or too_long:
            segment = current.strip()
            if segment:
                left_trim = len(current) - len(current.lstrip())
                right_trim = len(current.rstrip())
                pieces.append((buffer_start + left_trim, buffer_start + right_trim, segment))
            buffer_start = cursor + 1
        cursor += 1

    if buffer_start < len(text):
        current = text[buffer_start:]
        segment = current.strip()
        if segment:
            left_trim = len(current) - len(current.lstrip())
            right_trim = len(current.rstrip())
            pieces.append((buffer_start + left_trim, buffer_start + right_trim, segment))

    # Split any over-capacity segment at safe character boundaries.
    result: list[tuple[int, int, str]] = []
    for seg_start, seg_end, segment in pieces:
        if weighted_length(segment) <= capacity:
            result.append((seg_start, seg_end, segment))
            continue
        local_start = 0
        while local_start < len(segment):
            end = local_start
            while end < len(segment) and weighted_length(segment[local_start : end + 1]) <= capacity:
                end += 1
            if end >= len(segment):
                chunk = segment[local_start:].strip()
                if chunk:
                    left_trim = len(segment[local_start:]) - len(segment[local_start:].lstrip())
                    result.append((seg_start + local_start + left_trim, seg_end, chunk))
                break

            split_at = end
            # Keep contiguous Latin words and numbers intact whenever there is an earlier safe boundary.
            if split_at > local_start and split_at < len(segment):
                if segment[split_at - 1].isascii() and segment[split_at - 1].isalnum() and segment[split_at].isascii() and segment[split_at].isalnum():
                    probe = split_at
                    while probe > local_start and not segment[probe - 1].isspace() and segment[probe - 1] not in PUNCTUATION:
                        probe -= 1
                    if probe > local_start:
                        split_at = probe
            raw_chunk = segment[local_start:split_at]
            chunk = raw_chunk.strip()
            if not chunk:
                split_at = max(local_start + 1, end)
                raw_chunk = segment[local_start:split_at]
                chunk = raw_chunk.strip()
            left_trim = len(raw_chunk) - len(raw_chunk.lstrip())
            right_trim = len(raw_chunk.rstrip())
            if chunk:
                result.append((seg_start + local_start + left_trim, seg_start + local_start + right_trim, chunk))
            local_start = split_at
            while local_start < len(segment) and segment[local_start].isspace():
                local_start += 1
    return result


def proportional_time(scene: dict[str, Any], start_idx: int, end_idx: int) -> tuple[float, float]:
    text = scene["text"]
    duration = max(0.001, float(scene["audio_end"]) - float(scene["start"]))
    weights = [weighted_length(char) for char in text]
    total = sum(weights) or 1.0
    before = sum(weights[:start_idx])
    until = sum(weights[:end_idx])
    start = float(scene["start"]) + duration * before / total
    end = float(scene["start"]) + duration * until / total
    return start, end


def aligned_time(scene: dict[str, Any], start_idx: int, end_idx: int) -> tuple[float, float]:
    alignment = scene.get("alignment", {})
    text = scene["text"]
    if alignment.get("type") == "characters":
        chars = alignment.get("characters", [])
        starts = alignment.get("starts_global", [])
        ends = alignment.get("ends_global", [])
        if len(chars) == len(text) and len(starts) == len(chars) and len(ends) == len(chars):
            return float(starts[start_idx]), float(ends[max(start_idx, end_idx - 1)])
        if len(starts) == len(chars) and chars:
            # Map by relative character position when provider normalization changed the text.
            a = min(len(chars) - 1, round(start_idx / max(1, len(text)) * len(chars)))
            b = min(len(chars) - 1, max(a, round(end_idx / max(1, len(text)) * len(chars)) - 1))
            return float(starts[a]), float(ends[b])
    if alignment.get("type") == "words":
        words = alignment.get("words_global", [])
        if words:
            cumulative: list[int] = []
            total_chars = 0
            for word in words:
                total_chars += max(1, len(re.sub(r"\s+", "", str(word.get("text", "")))))
                cumulative.append(total_chars)
            target_start = start_idx / max(1, len(text)) * total_chars
            target_end = end_idx / max(1, len(text)) * total_chars
            start_word = next((i for i, value in enumerate(cumulative) if value >= target_start), 0)
            end_word = next((i for i, value in enumerate(cumulative) if value >= target_end), len(words) - 1)
            return float(words[start_word]["start"]), float(words[end_word]["end"])
    return proportional_time(scene, start_idx, end_idx)


def format_srt_time(seconds: float) -> str:
    ms = max(0, round(seconds * 1000))
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_ass_time(seconds: float) -> str:
    cs = max(0, round(seconds * 100))
    hours, rem = divmod(cs, 360_000)
    minutes, rem = divmod(rem, 6000)
    secs, centis = divmod(rem, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def escape_ass(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}").replace("\n", r"\N")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build SRT, ASS, and JSON subtitles from TTS timing data.")
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()

    project = args.project.resolve()
    paths = ensure_project_dirs(project)
    config = load_config(project, args.config.resolve() if args.config else None)
    timeline = load_json(paths["work"] / "audio-timeline.json")
    subtitle_cfg = config.get("subtitles", {})
    max_chars = int(subtitle_cfg.get("maxCharsPerLine", 16))
    max_lines = int(subtitle_cfg.get("maxLines", 2))

    cues: list[dict[str, Any]] = []
    for scene in timeline.get("scenes", []):
        segments = split_text(scene["text"], max_chars, max_lines)
        for start_idx, end_idx, segment in segments:
            start, end = aligned_time(scene, start_idx, end_idx)
            start = max(float(scene["start"]), start)
            end = min(float(scene["audio_end"]), max(end, start + 0.35))
            cues.append(
                {
                    "id": f"sub-{len(cues) + 1:04d}",
                    "scene_id": scene["id"],
                    "start": round(start, 3),
                    "end": round(end, 3),
                    "text": wrap_lines(segment, max_chars, max_lines),
                    "plain_text": segment,
                }
            )

    # Prevent overlap while retaining a small visual gap when possible.
    for idx, cue in enumerate(cues):
        if idx + 1 < len(cues):
            next_start = cues[idx + 1]["start"]
            if cue["end"] > next_start - 0.03:
                cue["end"] = max(cue["start"] + 0.2, next_start - 0.03)

    srt_lines: list[str] = []
    for index, cue in enumerate(cues, start=1):
        srt_lines.extend(
            [
                str(index),
                f"{format_srt_time(cue['start'])} --> {format_srt_time(cue['end'])}",
                cue["text"],
                "",
            ]
        )
    (paths["subtitles"] / "subtitles.srt").write_text("\n".join(srt_lines), encoding="utf-8")

    width, height, _ = parse_ratio(config)
    font = subtitle_cfg.get("font", "Noto Sans CJK SC")
    font_size = int(subtitle_cfg.get("fontSize", 52))
    margin_v = int(subtitle_cfg.get("bottomMargin", 72))
    outline = int(subtitle_cfg.get("outline", 3))
    ass_header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{font_size},&H00FFFFFF,&H00FFFFFF,&HCC111827,&H88111827,0,0,0,0,100,100,0,0,3,{outline},0,2,72,72,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ass_events = [
        f"Dialogue: 0,{format_ass_time(cue['start'])},{format_ass_time(cue['end'])},Default,,0,0,0,,{escape_ass(cue['text'])}"
        for cue in cues
    ]
    (paths["subtitles"] / "subtitles.ass").write_text(ass_header + "\n".join(ass_events) + "\n", encoding="utf-8")
    save_json(paths["work"] / "subtitles.json", {"version": 1, "cues": cues})
    print(f"[done] subtitle cues: {len(cues)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
