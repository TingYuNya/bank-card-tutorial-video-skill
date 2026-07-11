from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from utils import (
    ensure_project_dirs,
    ffprobe_duration,
    load_config,
    load_environment,
    load_json,
    require_binary,
    run,
    save_json,
)


def hash_payload(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def fallback_character_alignment(text: str, duration: float) -> dict[str, Any]:
    chars = list(text)
    if not chars:
        return {"type": "characters", "characters": [], "starts": [], "ends": [], "source": "fallback"}
    weights = [0.35 if ch.isspace() else 0.45 if ch in "，。！？；：,.!?;:" else 1.0 for ch in chars]
    total = sum(weights) or 1.0
    starts: list[float] = []
    ends: list[float] = []
    cursor = 0.0
    for weight in weights:
        starts.append(cursor)
        cursor += duration * weight / total
        ends.append(cursor)
    ends[-1] = duration
    return {"type": "characters", "characters": chars, "starts": starts, "ends": ends, "source": "fallback"}


def normalize_audio(source: Path, dest: Path, sample_rate: int, channels: int) -> None:
    require_binary("ffmpeg")
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-ar",
            str(sample_rate),
            "-ac",
            str(channels),
            "-c:a",
            "pcm_s16le",
            str(dest),
        ]
    )


def create_silence(dest: Path, seconds: float, sample_rate: int, channels: int) -> None:
    channel_layout = "stereo" if channels == 2 else "mono"
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r={sample_rate}:cl={channel_layout}",
            "-t",
            f"{seconds:.6f}",
            "-c:a",
            "pcm_s16le",
            str(dest),
        ]
    )


def tts_elevenlabs(text: str, out_raw: Path, config: dict[str, Any], previous_text: str, next_text: str) -> dict[str, Any]:
    import requests

    api_key = os.getenv("ELEVENLABS_API_KEY")
    voice_id = os.getenv("ELEVENLABS_VOICE_ID")
    if not api_key or not voice_id:
        raise RuntimeError("ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID are required")
    tts_config = config["tts"]["elevenlabs"]
    model = os.getenv("ELEVENLABS_MODEL_ID") or tts_config.get("model", "eleven_multilingual_v2")
    output_format = tts_config.get("outputFormat", "mp3_44100_128")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
    payload: dict[str, Any] = {
        "text": text,
        "model_id": model,
        "voice_settings": {
            "stability": tts_config.get("stability", 0.55),
            "similarity_boost": tts_config.get("similarityBoost", 0.75),
            "style": tts_config.get("style", 0.15),
            "use_speaker_boost": tts_config.get("speakerBoost", True),
        },
    }
    if previous_text:
        payload["previous_text"] = previous_text[-1000:]
    if next_text:
        payload["next_text"] = next_text[:1000]

    response = requests.post(
        url,
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        params={"output_format": output_format},
        json=payload,
        timeout=180,
    )
    response.raise_for_status()
    data = response.json()
    out_raw.write_bytes(base64.b64decode(data["audio_base64"]))
    alignment = data.get("normalized_alignment") or data.get("alignment")
    if not alignment:
        return {"type": "none", "source": "elevenlabs"}
    return {
        "type": "characters",
        "characters": alignment.get("characters", []),
        "starts": alignment.get("character_start_times_seconds", []),
        "ends": alignment.get("character_end_times_seconds", []),
        "source": "elevenlabs",
    }


def align_openai_whisper(audio_path: Path, model: str) -> dict[str, Any]:
    from openai import OpenAI

    client = OpenAI()
    with audio_path.open("rb") as audio_file:
        result = client.audio.transcriptions.create(
            file=audio_file,
            model=model,
            response_format="verbose_json",
            timestamp_granularities=["word"],
        )
    words = []
    for item in getattr(result, "words", []) or []:
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        words.append(
            {
                "text": str(item.get("word", "")),
                "start": float(item.get("start", 0)),
                "end": float(item.get("end", 0)),
            }
        )
    return {"type": "words", "words": words, "source": f"openai:{model}"}


def tts_openai(text: str, out_raw: Path, config: dict[str, Any]) -> dict[str, Any]:
    from openai import OpenAI

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required")
    tts_config = config["tts"]["openai"]
    model = os.getenv("OPENAI_TTS_MODEL") or tts_config.get("model", "gpt-4o-mini-tts")
    voice = os.getenv("OPENAI_TTS_VOICE") or tts_config.get("voice", "marin")
    instructions = os.getenv("OPENAI_TTS_INSTRUCTIONS") or tts_config.get("instructions", "")
    response_format = tts_config.get("responseFormat", "wav")
    client = OpenAI()
    with client.audio.speech.with_streaming_response.create(
        model=model,
        voice=voice,
        input=text,
        instructions=instructions,
        response_format=response_format,
    ) as response:
        response.stream_to_file(out_raw)
    return {"type": "none", "source": f"openai:{model}"}


def tts_azure(text: str, out_raw: Path, config: dict[str, Any]) -> dict[str, Any]:
    import azure.cognitiveservices.speech as speechsdk

    key = os.getenv("SPEECH_KEY")
    region = os.getenv("SPEECH_REGION")
    if not key or not region:
        raise RuntimeError("SPEECH_KEY and SPEECH_REGION are required")
    voice = os.getenv("AZURE_SPEECH_VOICE") or config["tts"]["azure"].get("voice", "zh-CN-XiaoxiaoNeural")

    speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
    speech_config.speech_synthesis_voice_name = voice
    speech_config.set_property(
        property_id=speechsdk.PropertyId.SpeechServiceResponse_RequestSentenceBoundary,
        value="true",
    )
    audio_config = speechsdk.audio.AudioOutputConfig(filename=str(out_raw))
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
    words: list[dict[str, Any]] = []

    def on_boundary(evt: Any) -> None:
        boundary_name = str(getattr(evt, "boundary_type", ""))
        if "Word" not in boundary_name and "word" not in boundary_name:
            return
        start = float(evt.audio_offset) / 10_000_000.0
        duration = float(getattr(evt, "duration", 0)) / 10_000_000.0
        words.append({"text": getattr(evt, "text", ""), "start": start, "end": start + duration})

    synthesizer.synthesis_word_boundary.connect(on_boundary)
    result = synthesizer.speak_text_async(text).get()
    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        details = getattr(result, "cancellation_details", None)
        raise RuntimeError(f"Azure synthesis failed: {details}")
    return {"type": "words", "words": words, "source": f"azure:{voice}"}


def shift_alignment(alignment: dict[str, Any], offset: float) -> dict[str, Any]:
    shifted = dict(alignment)
    if alignment.get("type") == "characters":
        shifted["starts_global"] = [offset + float(v) for v in alignment.get("starts", [])]
        shifted["ends_global"] = [offset + float(v) for v in alignment.get("ends", [])]
    elif alignment.get("type") == "words":
        shifted["words_global"] = [
            {**word, "start": offset + float(word.get("start", 0)), "end": offset + float(word.get("end", 0))}
            for word in alignment.get("words", [])
        ]
    return shifted


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate per-scene TTS, timing data, and a merged narration WAV.")
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--provider", choices=["elevenlabs", "openai", "azure"])
    parser.add_argument("--config", type=Path)
    parser.add_argument("--reuse", action="store_true")
    parser.add_argument("--no-align", action="store_true")
    args = parser.parse_args()

    project = args.project.resolve()
    paths = ensure_project_dirs(project)
    load_environment(project)
    config = load_config(project, args.config.resolve() if args.config else None)
    provider = args.provider or config.get("tts", {}).get("provider", "elevenlabs")
    narration = load_json(paths["work"] / "narration.json")
    scenes = narration.get("scenes", [])
    if not scenes:
        raise RuntimeError("work/narration.json contains no scenes")

    sample_rate = int(config.get("audio", {}).get("sampleRate", 48000))
    channels = int(config.get("audio", {}).get("channels", 2))
    require_binary("ffmpeg")
    require_binary("ffprobe")

    scene_records: list[dict[str, Any]] = []
    concat_files: list[Path] = []
    cursor = 0.0

    for index, scene in enumerate(scenes):
        scene_id = scene.get("id") or f"scene-{index + 1:03d}"
        text = re.sub(r"\s+", " ", str(scene.get("text", ""))).strip()
        if not text:
            raise RuntimeError(f"Empty narration text: {scene_id}")
        pause_after = float(scene.get("pause_after", config["tts"].get("scenePauseSeconds", 0.25)))
        previous_text = str(scenes[index - 1].get("text", "")) if index > 0 else ""
        next_text = str(scenes[index + 1].get("text", "")) if index + 1 < len(scenes) else ""

        provider_ext = ".mp3" if provider == "elevenlabs" else ".wav"
        raw_path = paths["audio_scenes"] / f"{scene_id}.raw{provider_ext}"
        wav_path = paths["audio_scenes"] / f"{scene_id}.wav"
        meta_path = paths["audio_scenes"] / f"{scene_id}.json"
        payload_hash = hash_payload({"provider": provider, "text": text, "config": config.get("tts", {})})

        alignment: dict[str, Any] = {"type": "none"}
        cache_hit = False
        if args.reuse and wav_path.exists() and meta_path.exists():
            meta = load_json(meta_path)
            if meta.get("payload_hash") == payload_hash:
                alignment = meta.get("alignment", {"type": "none", "source": "cache"})
                cache_hit = True
                print(f"[reuse] {scene_id}")

        if not cache_hit:
            print(f"[tts] {scene_id} via {provider}")
            raw_path.unlink(missing_ok=True)
            wav_path.unlink(missing_ok=True)
            if provider == "elevenlabs":
                alignment = tts_elevenlabs(text, raw_path, config, previous_text, next_text)
            elif provider == "openai":
                alignment = tts_openai(text, raw_path, config)
            else:
                alignment = tts_azure(text, raw_path, config)
            normalize_audio(raw_path, wav_path, sample_rate, channels)

        duration = ffprobe_duration(wav_path)
        if alignment.get("type") in {None, "none"}:
            should_align = (
                not args.no_align
                and provider == "openai"
                and os.getenv("OPENAI_API_KEY")
                and config.get("tts", {}).get("alignment") == "provider_or_openai_whisper"
            )
            if should_align:
                model = os.getenv("OPENAI_ALIGNMENT_MODEL") or "whisper-1"
                try:
                    alignment = align_openai_whisper(wav_path, model)
                except Exception as exc:  # Keep the render pipeline usable if alignment fails.
                    print(f"[warning] alignment failed for {scene_id}: {exc}")
                    alignment = fallback_character_alignment(text, duration)
            else:
                alignment = fallback_character_alignment(text, duration)

        start = cursor
        audio_end = start + duration
        end = audio_end + max(0.0, pause_after)
        shifted = shift_alignment(alignment, start)
        record = {
            "id": scene_id,
            "text": text,
            "start": round(start, 6),
            "audio_end": round(audio_end, 6),
            "end": round(end, 6),
            "duration": round(duration, 6),
            "pause_after": round(max(0.0, pause_after), 6),
            "audio_file": wav_path.relative_to(project).as_posix(),
            "alignment": shifted,
        }
        scene_records.append(record)
        save_json(meta_path, {"payload_hash": payload_hash, "provider": provider, "alignment": alignment, "duration": duration})
        concat_files.append(wav_path)

        if pause_after > 0:
            silence_path = paths["audio_scenes"] / f"{scene_id}.pause.wav"
            create_silence(silence_path, pause_after, sample_rate, channels)
            concat_files.append(silence_path)
        cursor = end

    concat_list = paths["audio"] / "concat.txt"
    with concat_list.open("w", encoding="utf-8") as fh:
        for item in concat_files:
            escaped = str(item).replace("'", "'\\''")
            fh.write(f"file '{escaped}'\n")

    raw_merged = paths["audio"] / "narration.raw.wav"
    final_audio = paths["audio"] / "narration.wav"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c:a", "pcm_s16le", str(raw_merged)])
    target_lufs = float(config.get("audio", {}).get("targetLufs", -16))
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(raw_merged),
            "-af",
            f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
            "-ar",
            str(sample_rate),
            "-ac",
            str(channels),
            "-c:a",
            "pcm_s16le",
            str(final_audio),
        ]
    )

    total_duration = ffprobe_duration(final_audio)
    timeline = {
        "version": 1,
        "provider": provider,
        "sample_rate": sample_rate,
        "channels": channels,
        "total_duration": round(total_duration, 6),
        "audio": final_audio.relative_to(project).as_posix(),
        "scenes": scene_records,
    }
    save_json(paths["work"] / "audio-timeline.json", timeline)
    save_json(paths["audio"] / "timings.json", timeline)
    print(f"[done] {final_audio}")
    print(f"[duration] {total_duration:.3f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
