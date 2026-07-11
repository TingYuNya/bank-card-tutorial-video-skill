from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Any

from utils import ensure_project_dirs, load_config, load_json, parse_ratio, save_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge storyboard, TTS timing, subtitles, and privacy redactions into a timeline.")
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()

    project = args.project.resolve()
    paths = ensure_project_dirs(project)
    config = load_config(project, args.config.resolve() if args.config else None)
    width, height, dpr = parse_ratio(config)
    audio_timeline = load_json(paths["work"] / "audio-timeline.json")
    storyboard = load_json(paths["work"] / "storyboard.json")
    subtitles = load_json(paths["work"] / "subtitles.json")
    privacy = load_json(paths["work"] / "privacy-review.json")

    audio_by_id = {item["id"]: item for item in audio_timeline.get("scenes", [])}
    redactions_by_asset = {item.get("asset"): item.get("redactions", []) for item in privacy.get("assets", [])}
    visuals_by_narration: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for scene in storyboard.get("scenes", []):
        visuals_by_narration[str(scene.get("narration_scene_id"))].append(scene)

    timeline_scenes: list[dict[str, Any]] = []
    for narration_id, audio_scene in audio_by_id.items():
        visuals = visuals_by_narration.get(narration_id, [])
        if not visuals:
            raise RuntimeError(f"No storyboard scene for narration scene {narration_id}")
        base_start = float(audio_scene["start"])
        base_end = float(audio_scene["end"])
        base_duration = max(0.001, base_end - base_start)

        narration_intervals: list[tuple[float, float, str]] = []
        for index, visual in enumerate(visuals):
            if "start_offset" in visual or "end_offset" in visual:
                start = base_start + float(visual.get("start_offset", 0.0))
                end = base_start + float(visual.get("end_offset", base_duration))
            elif len(visuals) == 1:
                start, end = base_start, base_end
            else:
                start = base_start + base_duration * index / len(visuals)
                end = base_start + base_duration * (index + 1) / len(visuals)

            scene_id = visual.get("id") or f"visual-{len(timeline_scenes) + 1:03d}"
            start = max(base_start, start)
            end = min(base_end, end)
            if end - start < 0.05:
                raise RuntimeError(f"Storyboard scene {scene_id} has an invalid or too-short interval")
            narration_intervals.append((start, end, scene_id))
            asset = visual.get("asset")
            scene_redactions = list(redactions_by_asset.get(asset, [])) + list(visual.get("redactions", []))
            timeline_scenes.append(
                {
                    "id": scene_id,
                    "narration_scene_id": narration_id,
                    "start": round(start, 6),
                    "end": round(end, 6),
                    "kind": visual.get("kind", "image" if asset else "card"),
                    "asset": asset,
                    "source_start": float(visual.get("source_start", 0.0)),
                    "task": visual.get("task", ""),
                    "screen_text": visual.get("screen_text", ""),
                    "motion": visual.get("motion", {"type": "zoom_in", "start_scale": 1.0, "end_scale": 1.06}),
                    "overlays": visual.get("overlays", []),
                    "redactions": scene_redactions,
                    "card": visual.get("card", {}),
                    "source_claim_ids": visual.get("source_claim_ids", []),
                }
            )

        narration_intervals.sort(key=lambda item: (item[0], item[1]))
        tolerance = 0.02
        if narration_intervals[0][0] > base_start + tolerance:
            raise RuntimeError(f"Storyboard for {narration_id} does not cover the beginning of its audio")
        if narration_intervals[-1][1] < base_end - tolerance:
            raise RuntimeError(f"Storyboard for {narration_id} does not cover the end of its audio")
        for previous, current in zip(narration_intervals, narration_intervals[1:]):
            delta = current[0] - previous[1]
            if delta > tolerance:
                raise RuntimeError(f"Storyboard gap for {narration_id}: {previous[2]} to {current[2]} ({delta:.3f}s)")
            if delta < -tolerance:
                raise RuntimeError(f"Storyboard overlap for {narration_id}: {previous[2]} and {current[2]} ({-delta:.3f}s)")

    timeline_scenes.sort(key=lambda item: (item["start"], item["end"]))
    total_duration = float(audio_timeline.get("total_duration", timeline_scenes[-1]["end"] if timeline_scenes else 0))
    output = {
        "version": 1,
        "canvas": {"width": width, "height": height, "dpr": dpr},
        "fps": int(config.get("fps", 30)),
        "total_duration": round(total_duration, 6),
        "audio": audio_timeline.get("audio", "audio/narration.wav"),
        "scenes": timeline_scenes,
        "subtitles": subtitles.get("cues", []),
        "style": {
            "visual": config.get("visual", {}),
            "subtitles": config.get("subtitles", {}),
            "privacy": config.get("privacy", {}),
        },
    }
    save_json(paths["work"] / "timeline.json", output)
    print(f"[done] timeline scenes: {len(timeline_scenes)}")
    print(f"[duration] {total_duration:.3f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
