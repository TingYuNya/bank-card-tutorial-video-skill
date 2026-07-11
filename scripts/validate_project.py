from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from utils import load_config, load_json, normalize_asset_path, project_paths

CARD_NUMBER_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
SENSITIVE_LABEL_RE = re.compile(r"\b(?:cvv|cvc|pin|otp|routing\s*number|account\s*number|iban|验证码|安全码|卡号|账户号)\b", re.I)
ALLOWED_CLAIM_STATUS = {"verified", "qualified", "removed", "unresolved"}
ALLOWED_SEVERITY = {"high", "medium", "low"}
ALLOWED_SOURCE_TYPES = {"bank_official", "card_network_official", "regulator", "product_agreement", "official_help", "official_app", "other_official"}


def add(errors: list[str], message: str) -> None:
    errors.append(message)


def check_initialized(project: Path, errors: list[str], warnings: list[str]) -> None:
    paths = project_paths(project)
    required = [
        paths["source"] / "tutorial.original.md",
        paths["work"] / "manifest.json",
        paths["work"] / "sections.json",
    ]
    for path in required:
        if not path.exists():
            add(errors, f"Missing required file: {path}")

    manifest_path = paths["work"] / "manifest.json"
    if manifest_path.exists():
        manifest = load_json(manifest_path)
        missing = manifest.get("missing_assets", [])
        if missing:
            for item in missing:
                add(errors, f"Missing asset at line {item.get('line')}: {item.get('target')} ({item.get('reason')})")
        for item in manifest.get("assets", []):
            asset = normalize_asset_path(project, item["path"])
            if not asset.exists():
                add(errors, f"Manifest asset does not exist: {item['path']}")

    source_md = paths["source"] / "tutorial.original.md"
    if source_md.exists():
        text = source_md.read_text(encoding="utf-8")
        for match in CARD_NUMBER_RE.finditer(text):
            warnings.append(f"Possible card/account number in Markdown near: {match.group(0)[:8]}...")
        if SENSITIVE_LABEL_RE.search(text):
            warnings.append("Markdown contains sensitive-field labels. Confirm that no live credentials are included.")


def check_fact_check(project: Path, config: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    path = project / "work" / "fact-check.json"
    if not path.exists():
        add(errors, "Missing work/fact-check.json")
        return
    data = load_json(path)
    claims = data.get("claims", [])
    if not claims:
        add(errors, "fact-check.json contains no claims")
        return

    seen: set[str] = set()
    for index, claim in enumerate(claims, start=1):
        cid = claim.get("id") or f"claim #{index}"
        if cid in seen:
            add(errors, f"Duplicate claim id: {cid}")
        seen.add(cid)
        status = claim.get("status")
        severity = claim.get("severity")
        if status not in ALLOWED_CLAIM_STATUS:
            add(errors, f"{cid}: invalid status {status!r}")
        if severity not in ALLOWED_SEVERITY:
            add(errors, f"{cid}: invalid severity {severity!r}")
        if status in {"verified", "qualified"}:
            source_url = str(claim.get("source_url", ""))
            source_type = claim.get("source_type")
            source_language = str(claim.get("source_language", ""))
            if not source_url or not claim.get("source_title"):
                add(errors, f"{cid}: verified/qualified claim requires source_title and source_url")
            elif not source_url.startswith("https://"):
                add(errors, f"{cid}: source_url must use HTTPS")
            if source_type not in ALLOWED_SOURCE_TYPES:
                add(errors, f"{cid}: source_type must be one of {sorted(ALLOWED_SOURCE_TYPES)}")
            if config.get("factCheck", {}).get("officialSourcesOnly", True) and claim.get("source_official") is not True:
                add(errors, f"{cid}: source_official=true is required")
            if not source_language:
                add(errors, f"{cid}: source_language is required")
            if source_language.lower().startswith("zh") and not config.get("factCheck", {}).get("allowChineseSources", False):
                add(errors, f"{cid}: Chinese-language source is disabled by configuration")
            if config.get("factCheck", {}).get("checkedAtRequired", True) and not claim.get("checked_at"):
                add(errors, f"{cid}: checked_at is required")
        if status == "unresolved" and severity == "high" and config.get("factCheck", {}).get("blockHighRiskUnresolved", True):
            add(errors, f"{cid}: unresolved high-risk claim blocks rendering")
        if status == "removed" and not claim.get("notes"):
            warnings.append(f"{cid}: removed claim has no explanation")


def check_privacy(project: Path, config: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    manifest_path = project / "work" / "manifest.json"
    privacy_path = project / "work" / "privacy-review.json"
    if not privacy_path.exists():
        add(errors, "Missing work/privacy-review.json")
        return
    privacy = load_json(privacy_path)
    reviewed = {item.get("asset"): item for item in privacy.get("assets", [])}
    manifest = load_json(manifest_path, {"assets": []})
    for asset in manifest.get("assets", []):
        rel = asset.get("path")
        item = reviewed.get(rel)
        if not item:
            add(errors, f"Asset missing privacy review: {rel}")
            continue
        if config.get("privacy", {}).get("requireReviewForEveryAsset", True) and item.get("reviewed") is not True:
            add(errors, f"Asset privacy review incomplete: {rel}")
        if item.get("contains_sensitive_data") is True and not item.get("redactions"):
            add(errors, f"Sensitive asset has no redaction rectangles: {rel}")
        for ridx, redaction in enumerate(item.get("redactions", []), start=1):
            for key in ["x", "y", "w", "h"]:
                value = redaction.get(key)
                if not isinstance(value, (int, float)) or value < 0 or value > 1:
                    add(errors, f"{rel} redaction #{ridx}: {key} must be within 0..1")
            if redaction.get("x", 0) + redaction.get("w", 0) > 1.001:
                add(errors, f"{rel} redaction #{ridx}: x+w exceeds image bounds")
            if redaction.get("y", 0) + redaction.get("h", 0) > 1.001:
                add(errors, f"{rel} redaction #{ridx}: y+h exceeds image bounds")


def check_narration_storyboard(project: Path, errors: list[str], warnings: list[str]) -> None:
    narration_path = project / "work" / "narration.json"
    storyboard_path = project / "work" / "storyboard.json"
    for path in [narration_path, storyboard_path]:
        if not path.exists():
            add(errors, f"Missing {path.relative_to(project)}")
    if not narration_path.exists() or not storyboard_path.exists():
        return

    narration = load_json(narration_path)
    storyboard = load_json(storyboard_path)
    fact_data = load_json(project / "work" / "fact-check.json", {"claims": []})
    valid_claim_ids = {claim.get("id") for claim in fact_data.get("claims", []) if claim.get("id")}
    scenes = narration.get("scenes", [])
    if not scenes:
        add(errors, "narration.json contains no scenes")
        return
    nids = {scene.get("id") for scene in scenes}
    if None in nids or len(nids) != len(scenes):
        add(errors, "Narration scene IDs must be present and unique")
    for scene in scenes:
        if not str(scene.get("text", "")).strip():
            add(errors, f"Narration scene has empty text: {scene.get('id')}")

    visual_scenes = storyboard.get("scenes", [])
    if not visual_scenes:
        add(errors, "storyboard.json contains no scenes")
        return
    covered: set[str] = set()
    for scene in visual_scenes:
        sid = scene.get("narration_scene_id")
        if sid not in nids:
            add(errors, f"Storyboard references unknown narration scene: {sid}")
        else:
            covered.add(sid)
        claim_ids = scene.get("source_claim_ids", [])
        if not claim_ids and not str(scene.get("fact_check_exempt_reason", "")).strip():
            add(errors, f"Storyboard {scene.get('id')} requires source_claim_ids or fact_check_exempt_reason")
        for claim_id in claim_ids:
            if claim_id not in valid_claim_ids:
                add(errors, f"Storyboard {scene.get('id')} references unknown claim: {claim_id}")
        asset = scene.get("asset")
        if asset:
            path = normalize_asset_path(project, asset)
            if not path.exists():
                add(errors, f"Storyboard asset missing: {asset}")
        for overlay in scene.get("overlays", []):
            if overlay.get("type") in {"rect", "label", "arrow"}:
                for key in ["x", "y"]:
                    value = overlay.get(key)
                    if value is not None and (not isinstance(value, (int, float)) or value < 0 or value > 1):
                        add(errors, f"Storyboard {scene.get('id')} overlay {key} must be within 0..1")
    missing = sorted(nids - covered)
    if missing:
        add(errors, f"Narration scenes missing storyboard coverage: {', '.join(missing)}")


def check_reviews(project: Path, config: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    mode = config.get("approvalMode", "user")
    for name in ["storyboard-review.json", "timeline-review.json"]:
        path = project / "work" / name
        if not path.exists():
            add(errors, f"Missing review approval: work/{name}")
            continue
        data = load_json(path)
        if data.get("approved") is not True:
            add(errors, f"Review not approved: work/{name}")
        if mode == "user" and data.get("approved_by") not in {"user", "human"}:
            warnings.append(f"{name} approvalMode=user but approved_by={data.get('approved_by')!r}")


def check_render_inputs(project: Path, errors: list[str], warnings: list[str]) -> None:
    required = [
        project / "audio" / "narration.wav",
        project / "work" / "audio-timeline.json",
        project / "work" / "subtitles.json",
        project / "work" / "timeline.json",
        project / "renders" / "final-player.html",
    ]
    for path in required:
        if not path.exists():
            add(errors, f"Missing render input: {path.relative_to(project)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a tutorial video project.")
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--phase", choices=["initialized", "content", "render"], default="content")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--allow-warnings", action="store_true")
    args = parser.parse_args()

    project = args.project.resolve()
    config = load_config(project, args.config.resolve() if args.config else None)
    errors: list[str] = []
    warnings: list[str] = []

    check_initialized(project, errors, warnings)
    if args.phase in {"content", "render"}:
        check_fact_check(project, config, errors, warnings)
        check_privacy(project, config, errors, warnings)
        check_narration_storyboard(project, errors, warnings)
    if args.phase == "render":
        check_reviews(project, config, errors, warnings)
        check_render_inputs(project, errors, warnings)

    for warning in warnings:
        print(f"[warning] {warning}")
    for error in errors:
        print(f"[error] {error}")

    if errors:
        print(f"[failed] {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    print(f"[ok] validation passed with {len(warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
