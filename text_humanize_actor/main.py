"""Apify Actor entry point for TextHumanize."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from apify import Actor

from .processor import (
    LIBRARY_VERSION,
    build_summary,
    collect_texts,
    error_item,
    parse_settings,
    process_one,
)


async def main() -> None:
    """Run the TextHumanize Actor."""
    async with Actor:
        raw_input = await Actor.get_input() or {}

        settings = parse_settings(raw_input)
        texts = collect_texts(raw_input)

        Actor.log.info(
            "TextHumanize %s | mode=%s | texts=%d | language=%s | profile=%s | intensity=%d",
            LIBRARY_VERSION,
            settings.mode,
            len(texts),
            settings.language,
            settings.profile,
            settings.intensity,
        )

        started_at = time.perf_counter()
        semaphore = asyncio.Semaphore(settings.concurrency)

        async def process(index: int, text: str) -> dict[str, Any]:
            async with semaphore:
                try:
                    return await asyncio.to_thread(
                        process_one, settings.mode, text, settings, index
                    )
                except Exception as exc:
                    Actor.log.warning(
                        "Text %d/%d failed: %s: %s",
                        index + 1,
                        len(texts),
                        type(exc).__name__,
                        exc,
                    )
                    return error_item(settings.mode, index, text, exc)

        tasks = [asyncio.create_task(process(index, text)) for index, text in enumerate(texts)]

        items: list[dict[str, Any]] = []
        for position, task in enumerate(tasks, start=1):
            item = await task
            items.append(item)
            await Actor.push_data(item)
            Actor.log.info(
                "Processed %d/%d (%s)",
                position,
                len(tasks),
                "failed" if "error" in item else "ok",
            )

        summary = build_summary(items, settings, time.perf_counter() - started_at)
        await Actor.set_value("SUMMARY", summary)

        Actor.log.info(
            "Finished: %d succeeded, %d failed in %.1fs",
            summary["succeeded"],
            summary["failed"],
            summary["elapsedSeconds"],
        )

        if summary["failed"] and not summary["succeeded"]:
            raise RuntimeError(
                f"All {summary['failed']} text(s) failed. "
                "See the run's dataset for error details."
            )
