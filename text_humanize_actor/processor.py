"""Core processing logic for the TextHumanize Apify Actor.

This module intentionally has no Apify SDK imports so it can also be used
from plain Python (tests, scripts, other wrappers).
"""

from __future__ import annotations

import dataclasses
from typing import Any

from texthumanize import __version__ as LIBRARY_VERSION
from texthumanize import analyze as analyze_text
from texthumanize import detect_ai, humanize

MODES = ("humanize", "detect", "analyze")

PROFILES = (
    "chat",
    "web",
    "seo",
    "docs",
    "formal",
    "academic",
    "marketing",
    "social",
    "email",
)

LANGUAGES = (
    "ar",
    "cs",
    "da",
    "de",
    "en",
    "es",
    "fr",
    "he",
    "hi",
    "hu",
    "id",
    "it",
    "ja",
    "ko",
    "nl",
    "pl",
    "pt",
    "ro",
    "ru",
    "sv",
    "th",
    "tr",
    "uk",
    "vi",
    "zh",
)

MAX_ERROR_TEXT_CHARS = 2000


@dataclasses.dataclass
class Settings:
    """Normalized Actor input."""

    mode: str = "humanize"
    language: str = "auto"
    profile: str = "web"
    intensity: int = 60
    quality_gate: str | None = None
    minimal: bool = False
    phantom: bool = False
    include_detection: bool = True
    target_style: str | None = None
    seed: int | None = None
    keep_keywords: list[str] = dataclasses.field(default_factory=list)
    protect_terms: list[str] = dataclasses.field(default_factory=list)
    concurrency: int = 1


def parse_settings(raw: dict[str, Any]) -> Settings:
    """Build validated :class:`Settings` from a raw Actor input object."""
    mode = str(raw.get("mode") or "humanize").strip().lower()
    if mode not in MODES:
        raise ValueError(f"Unknown mode '{mode}'. Expected one of: {', '.join(MODES)}.")

    quality_gate = str(raw.get("qualityGate") or "none").strip().lower()
    if quality_gate not in ("none", "strict"):
        raise ValueError("'qualityGate' must be 'none' or 'strict'.")

    return Settings(
        mode=mode,
        language=str(raw.get("language") or "auto").strip() or "auto",
        profile=str(raw.get("profile") or "web").strip().lower() or "web",
        intensity=_clamp_int(raw.get("intensity"), 0, 100, 60),
        quality_gate=None if quality_gate == "none" else quality_gate,
        minimal=_as_bool(raw.get("minimal"), default=False),
        phantom=_as_bool(raw.get("phantom"), default=False),
        include_detection=_as_bool(raw.get("includeDetection"), default=True),
        target_style=_optional_str(raw.get("targetStyle")),
        seed=_optional_int(raw.get("seed")),
        keep_keywords=_as_str_list(raw.get("keepKeywords")),
        protect_terms=_as_str_list(raw.get("protectTerms")),
        concurrency=_clamp_int(raw.get("concurrency"), 1, 8, 1),
    )


def collect_texts(raw: dict[str, Any]) -> list[str]:
    """Return the list of texts to process from the raw Actor input."""
    texts = raw.get("texts")
    if texts:
        if isinstance(texts, str):
            texts = [texts]
        if not isinstance(texts, (list, tuple)):
            raise ValueError("'texts' must be a list of strings.")
        invalid = [item for item in texts if not isinstance(item, str)]
        if invalid:
            raise ValueError("Every item in 'texts' must be a string.")
        cleaned = [item for item in texts if item.strip()]
        if cleaned:
            return cleaned

    text = raw.get("text")
    if isinstance(text, str) and text.strip():
        return [text]

    raise ValueError("No text to process: fill in 'Text' or 'Texts' in the Actor input.")


def process_one(mode: str, text: str, settings: Settings, index: int) -> dict[str, Any]:
    """Process a single text and return a dataset-ready item."""
    if mode == "detect":
        return _detect_item(text, settings, index)
    if mode == "analyze":
        return _analyze_item(text, settings, index)
    return _humanize_item(text, settings, index)


def error_item(mode: str, index: int, text: str, exc: BaseException) -> dict[str, Any]:
    """Build a dataset item describing a failed text."""
    if len(text) > MAX_ERROR_TEXT_CHARS:
        text = text[:MAX_ERROR_TEXT_CHARS] + "…"
    return {
        "type": mode,
        "index": index,
        "original": text,
        "error": f"{type(exc).__name__}: {exc}",
    }


def build_summary(
    items: list[dict[str, Any]],
    settings: Settings,
    elapsed_seconds: float,
) -> dict[str, Any]:
    """Build the run summary stored under the SUMMARY key-value store key."""
    succeeded = [item for item in items if "error" not in item]
    failed = [item for item in items if "error" in item]

    summary: dict[str, Any] = {
        "actor": "text-humanize",
        "libraryVersion": LIBRARY_VERSION,
        "mode": settings.mode,
        "language": settings.language,
        "profile": settings.profile,
        "intensity": settings.intensity,
        "inputTexts": len(items),
        "succeeded": len(succeeded),
        "failed": len(failed),
        "totalInputCharacters": sum(len(item.get("original") or "") for item in items),
        "elapsedSeconds": round(elapsed_seconds, 2),
    }

    if settings.mode == "humanize":
        qualities = _numbers(item.get("qualityScore") for item in succeeded)
        if qualities:
            summary["averageQualityScore"] = round(sum(qualities) / len(qualities), 4)
        before = _numbers(item.get("aiProbabilityBefore") for item in succeeded)
        if before:
            summary["averageAiProbabilityBefore"] = round(sum(before) / len(before), 4)
        after = _numbers(item.get("aiProbabilityAfter") for item in succeeded)
        if after:
            summary["averageAiProbabilityAfter"] = round(sum(after) / len(after), 4)

    if failed:
        summary["errors"] = [
            {"index": item["index"], "error": item["error"]} for item in failed[:20]
        ]

    return summary


def _humanize_item(text: str, settings: Settings, index: int) -> dict[str, Any]:
    preserve: dict[str, Any] = {}
    if settings.protect_terms:
        preserve["brand_terms"] = list(settings.protect_terms)

    constraints: dict[str, Any] = {}
    if settings.keep_keywords:
        constraints["keep_keywords"] = list(settings.keep_keywords)

    result = humanize(
        text,
        lang=settings.language,
        profile=settings.profile,
        intensity=settings.intensity,
        preserve=preserve or None,
        constraints=constraints or None,
        seed=None if settings.seed is None else settings.seed + index,
        target_style=settings.target_style,
        minimal=settings.minimal,
        quality_gate=settings.quality_gate,
        phantom=settings.phantom,
    )

    item: dict[str, Any] = {
        "type": "humanize",
        "index": index,
        "language": result.lang,
        "profile": result.profile,
        "intensity": result.intensity,
        "original": text,
        "result": result.text,
        "qualityScore": _round(result.quality_score),
        "changeRatio": _round(result.change_ratio),
        "similarity": _round(result.similarity),
        "changes": result.changes,
        "metricsBefore": _round_deep(result.metrics_before),
        "metricsAfter": _round_deep(result.metrics_after),
    }

    if settings.include_detection:
        before = _detection_summary(detect_ai(text, lang=settings.language))
        after = _detection_summary(detect_ai(result.text, lang=result.lang))
        item["aiProbabilityBefore"] = before["aiProbability"]
        item["aiProbabilityAfter"] = after["aiProbability"]
        item["verdictBefore"] = before["verdict"]
        item["verdictAfter"] = after["verdict"]
        item["detectionBefore"] = before
        item["detectionAfter"] = after

    return item


def _detect_item(text: str, settings: Settings, index: int) -> dict[str, Any]:
    summary = _detection_summary(detect_ai(text, lang=settings.language))
    item: dict[str, Any] = {
        "type": "detect",
        "index": index,
        "original": text,
    }
    item.update(summary)
    return item


def _analyze_item(text: str, settings: Settings, index: int) -> dict[str, Any]:
    report = analyze_text(text, lang=settings.language)
    return {
        "type": "analyze",
        "index": index,
        "language": report.lang,
        "original": text,
        "analysis": _round_deep(dataclasses.asdict(report)),
    }


def _detection_summary(detection: dict[str, Any]) -> dict[str, Any]:
    probability = detection.get("combined_score", detection.get("score"))
    probability = _round(probability) if probability is not None else None
    summary: dict[str, Any] = {
        "language": detection.get("lang"),
        "aiProbability": probability,
        "verdict": detection.get("verdict"),
        "confidence": _round(detection.get("confidence")),
        "domain": detection.get("domain"),
        "metrics": _round_deep(detection.get("metrics") or {}),
        "explanations": detection.get("explanations") or [],
    }
    if probability is not None:
        summary["humanProbability"] = round(1.0 - probability, 4)
    return summary


def _clamp_int(value: Any, minimum: int, maximum: int, default: int) -> int:
    parsed = _optional_int(value)
    if parsed is None:
        return default
    return max(minimum, min(maximum, parsed))


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def _as_str_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        parts = value.split(",")
    elif isinstance(value, (list, tuple)):
        parts = [str(item) for item in value]
    else:
        parts = [str(value)]
    return [part.strip() for part in parts if part.strip()]


def _numbers(values: Any) -> list[float]:
    return [float(value) for value in values if isinstance(value, (int, float))]


def _round(value: Any) -> float | Any:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return value


def _round_deep(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, dict):
        return {key: _round_deep(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_round_deep(item) for item in value]
    return value
