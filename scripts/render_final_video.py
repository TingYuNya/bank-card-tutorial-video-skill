from __future__ import annotations

import argparse
import json
import shutil
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

from serve_preview import PreviewHandler
from utils import (
    ensure_project_dirs,
    load_config,
    load_json,
    parse_ratio,
    require_binary,
    run,
)


def start_server(project: Path) -> tuple[ThreadingHTTPServer, threading.Thread, int]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), PreviewHandler)
    server.project_root = project  # type: ignore[attr-defined]
    port = int(server.server_address[1])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, port


def verify_approvals(project: Path, approval_mode: str) -> None:
    for name in ["storyboard-review.json", "timeline-review.json"]:
        path = project / "work" / name
        if not path.exists():
            raise RuntimeError(f"Missing approval file: {path}")
        data = load_json(path)
        if data.get("approved") is not True:
            raise RuntimeError(f"Review is not approved: {path}")
        if approval_mode == "user" and data.get("approved_by") not in {"user", "human"}:
            print(f"[warning] {name} approved_by={data.get('approved_by')!r} while approvalMode=user")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render deterministic frames in Playwright and encode the final MP4.")
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fps", type=int)
    parser.add_argument("--frame-format", choices=["png", "jpeg"])
    parser.add_argument("--crf", type=int)
    parser.add_argument("--preset")
    parser.add_argument("--keep-frames", action="store_true")
    parser.add_argument("--chrome-executable", type=Path)
    args = parser.parse_args()

    project = args.project.resolve()
    paths = ensure_project_dirs(project)
    config = load_config(project, args.config.resolve() if args.config else None)
    timeline = load_json(paths["work"] / "timeline.json")
    width, height, dpr = parse_ratio(config)
    fps = int(args.fps or timeline.get("fps") or config.get("fps", 30))
    render_cfg = config.get("render", {})
    frame_format = args.frame_format or render_cfg.get("frameFormat", "png")
    frame_ext = "png" if frame_format == "png" else "jpg"
    crf = str(args.crf or render_cfg.get("crf", 14))
    preset = args.preset or render_cfg.get("preset", "slow")
    audio_bitrate = render_cfg.get("audioBitrate", "192k")
    keep_frames = args.keep_frames or bool(render_cfg.get("keepFrames", False))
    total_duration = float(timeline.get("total_duration", 0))
    if total_duration <= 0:
        raise RuntimeError("timeline total_duration must be positive")

    verify_approvals(project, config.get("approvalMode", "user"))
    require_binary("ffmpeg")
    require_binary("ffprobe")

    player = paths["renders"] / "final-player.html"
    narration = project / timeline.get("audio", "audio/narration.wav")
    if not player.exists():
        raise FileNotFoundError(player)
    if not narration.exists():
        raise FileNotFoundError(narration)

    frames_dir = paths["renders"] / "frames"
    shutil.rmtree(frames_dir, ignore_errors=True)
    frames_dir.mkdir(parents=True, exist_ok=True)
    output = args.output.resolve() if args.output else paths["renders"] / "银行卡教程-final.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    video_only = paths["renders"] / "video-only.mp4"

    server, thread, port = start_server(project)
    frame_count = int(total_duration * fps + 0.999999)
    print(f"[render] canvas={width}x{height} dpr={dpr} output={round(width*dpr)}x{round(height*dpr)} fps={fps}")
    print(f"[render] frames={frame_count} format={frame_format} crf={crf} preset={preset}")

    try:
        with sync_playwright() as p:
            launch_args = {"headless": True}
            if args.chrome_executable:
                launch_args["executable_path"] = str(args.chrome_executable.resolve())
            browser = p.chromium.launch(**launch_args)
            context = browser.new_context(
                viewport={"width": width, "height": height},
                device_scale_factor=dpr,
                reduced_motion="reduce",
            )
            page = context.new_page()
            page.set_default_timeout(0)
            page.goto(f"http://127.0.0.1:{port}/renders/final-player.html?render=1", wait_until="domcontentloaded")
            page.wait_for_function("typeof window.seekTo === 'function' && Boolean(window.finalVideo)")
            page.evaluate("async () => { if (window.__readyPromise) await window.__readyPromise; }")
            stage = page.locator("#stage")

            for index in range(frame_count):
                time = index / fps
                page.evaluate("async (t) => await window.seekTo(t)", time)
                frame_path = frames_dir / f"frame-{index:06d}.{frame_ext}"
                options = {"path": str(frame_path), "type": frame_format, "scale": "device"}
                if frame_format == "jpeg":
                    options["quality"] = 96
                stage.screenshot(**options)
                if index % 150 == 0 or index == frame_count - 1:
                    print(f"[frames] {index + 1}/{frame_count} ({(index + 1) / frame_count * 100:.1f}%)")
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    run(
        [
            "ffmpeg",
            "-y",
            "-framerate",
            str(fps),
            "-i",
            str(frames_dir / f"frame-%06d.{frame_ext}"),
            "-c:v",
            "libx264",
            "-preset",
            str(preset),
            "-crf",
            crf,
            "-pix_fmt",
            "yuv420p",
            str(video_only),
        ]
    )

    bgm_value = config.get("audio", {}).get("backgroundMusic")
    if bgm_value:
        bgm = (project / bgm_value).resolve()
        if not bgm.exists():
            raise FileNotFoundError(f"Configured background music does not exist: {bgm}")
        volume = float(config.get("audio", {}).get("backgroundMusicVolume", 0.08))
        filter_complex = (
            f"[2:a]volume={volume},atrim=0:{total_duration},asetpts=N/SR/TB[bg];"
            f"[1:a][bg]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
        run(
            [
                "ffmpeg", "-y", "-i", str(video_only), "-i", str(narration), "-stream_loop", "-1", "-i", str(bgm),
                "-filter_complex", filter_complex,
                "-map", "0:v:0", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-b:a", str(audio_bitrate),
                "-shortest", str(output),
            ]
        )
    else:
        run(
            [
                "ffmpeg", "-y", "-i", str(video_only), "-i", str(narration),
                "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", str(audio_bitrate),
                "-shortest", str(output),
            ]
        )

    if not keep_frames:
        shutil.rmtree(frames_dir, ignore_errors=True)
        video_only.unlink(missing_ok=True)
    print(f"[done] {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
