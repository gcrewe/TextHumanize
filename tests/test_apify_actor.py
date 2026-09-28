"""Tests for the Apify Actor wrapper (``text_humanize_actor``)."""

from __future__ import annotations

import pytest

from text_humanize_actor.processor import (
    build_summary,
    collect_texts,
    error_item,
    parse_settings,
    process_one,
)


class TestParseSettings:
    def test_defaults(self):
        settings = parse_settings({})
        assert settings.mode == "humanize"
        assert settings.language == "auto"
        assert settings.profile == "web"
        assert settings.intensity == 60
        assert settings.quality_gate is None
        assert settings.minimal is False
        assert settings.phantom is False
        assert settings.include_detection is True
        assert settings.seed is None
        assert settings.concurrency == 1

    def test_overrides(self):
        settings = parse_settings(
            {
                "mode": "DETECT",
                "language": "en",
                "profile": "seo",
                "intensity": 150,
                "qualityGate": "strict",
                "includeDetection": False,
                "keepKeywords": ["tulum", " cenotes "],
                "protectTerms": "Riviera Maya, Cancún",
                "seed": 42,
                "concurrency": 20,
            }
        )
        assert settings.mode == "detect"
        assert settings.intensity == 100
        assert settings.quality_gate == "strict"
        assert settings.include_detection is False
        assert settings.keep_keywords == ["tulum", "cenotes"]
        assert settings.protect_terms == ["Riviera Maya", "Cancún"]
        assert settings.seed == 42
        assert settings.concurrency == 8

    def test_unknown_mode_is_rejected(self):
        with pytest.raises(ValueError):
            parse_settings({"mode": "rewrite"})


class TestCollectTexts:
    def test_single_text(self):
        assert collect_texts({"text": " hello "}) == [" hello "]

    def test_batch_takes_precedence(self):
        assert collect_texts({"text": "a", "texts": [" b ", "c"]}) == [" b ", "c"]

    def test_blank_text_is_rejected(self):
        with pytest.raises(ValueError):
            collect_texts({"text": "   "})

    def test_missing_text_is_rejected(self):
        with pytest.raises(ValueError):
            collect_texts({})

    def test_batch_rejects_non_strings(self):
        with pytest.raises(ValueError):
            collect_texts({"texts": ["ok", 42]})


class TestErrorItem:
    def test_describes_failure(self):
        item = error_item("humanize", 3, "short", ValueError("boom"))
        assert item == {
            "type": "humanize",
            "index": 3,
            "original": "short",
            "error": "ValueError: boom",
        }

    def test_truncates_long_text(self):
        item = error_item("humanize", 0, "x" * 5000, ValueError("boom"))
        assert len(item["original"]) == 2001


class TestBuildSummary:
    def test_counts_and_averages(self):
        settings = parse_settings({"mode": "humanize"})
        items = [
            {
                "index": 0,
                "original": "abc",
                "qualityScore": 0.8,
                "aiProbabilityBefore": 0.9,
                "aiProbabilityAfter": 0.2,
            },
            {"index": 1, "original": "de", "error": "Boom"},
        ]
        summary = build_summary(items, settings, elapsed_seconds=1.234)
        assert summary["succeeded"] == 1
        assert summary["failed"] == 1
        assert summary["inputTexts"] == 2
        assert summary["totalInputCharacters"] == 5
        assert summary["averageQualityScore"] == 0.8
        assert summary["averageAiProbabilityBefore"] == 0.9
        assert summary["averageAiProbabilityAfter"] == 0.2
        assert summary["elapsedSeconds"] == 1.23
        assert summary["errors"] == [{"index": 1, "error": "Boom"}]


class TestProcessOne:
    def test_humanize_smoke(self):
        settings = parse_settings(
            {"profile": "seo", "intensity": 40, "includeDetection": False}
        )
        item = process_one("humanize", "Данный текст является примером.", settings, 0)
        assert item["type"] == "humanize"
        assert item["index"] == 0
        assert item["original"] == "Данный текст является примером."
        assert isinstance(item["result"], str) and item["result"]
        assert 0.0 <= item["qualityScore"] <= 1.0
        assert "changes" in item and "metricsBefore" in item and "metricsAfter" in item
        assert "aiProbabilityBefore" not in item

    def test_detect_smoke(self):
        settings = parse_settings({"mode": "detect", "language": "en"})
        item = process_one("detect", "This is a short test sentence.", settings, 0)
        assert item["type"] == "detect"
        assert 0.0 <= item["aiProbability"] <= 1.0
        assert item["verdict"] in {"human", "mixed", "ai"}
        assert item["original"] == "This is a short test sentence."

    def test_analyze_smoke(self):
        settings = parse_settings({"mode": "analyze", "language": "en"})
        item = process_one("analyze", "This is a short test sentence.", settings, 0)
        assert item["type"] == "analyze"
        assert "artificiality_score" in item["analysis"]
