# TextHumanize — AI text humanizer & AI detector

Runs the [TextHumanize](https://github.com/gcrewe/TextHumanize) library as an Apify Actor:
turn AI-sounding text into natural human-like writing, estimate how AI-like a text is, and
inspect style and artificiality metrics. Fully offline — 38-stage pipeline, 25 languages.

## Modes

| Mode | What it does |
| --- | --- |
| `humanize` (default) | Rewrites each text with the 38-stage pipeline and returns the humanized result, change metrics, and (optionally) AI-detection scores before and after. |
| `detect` | Returns the AI probability, verdict (`human` / `mixed` / `ai`), confidence, domain, and detector metrics for each text. |
| `analyze` | Returns style and artificiality metrics (sentence length, bureaucracy ratio, repetition, typography, readability, etc.). |

## Input

Provide a single `Text`, or a `Texts` (batch) list — in batch mode each item is processed
separately and stored as its own dataset item. Key options:

- **Language** — `auto` (default) or one of 25 supported language codes.
- **Profile** — `chat`, `web` (default), `seo`, `docs`, `formal`, `academic`, `marketing`, `social`, `email`.
- **Intensity** — 0–100, how aggressively the text is rewritten (default 60).
- **Quality gate** — `strict` reverts changes that hurt similarity, grammar or readability.
- **Minimal changes** — rewrite only sentences flagged as AI-like.
- **PHANTOM™** — extra neural optimization pass that lowers AI-detection scores (slower).
- **Include AI detection** — report AI probability before/after each humanization.
- **Keep keywords / Protect terms** — SEO keywords and brand terms that must survive the rewrite.
- **Seed** — reproducible output.
- **Batch concurrency** — 1–8 texts processed in parallel.

Only `Text` / `Texts` is required; everything else has sensible defaults.

## Output

Results are stored in the default **dataset** — one item per text:

```json
{
    "type": "humanize",
    "index": 0,
    "language": "en",
    "profile": "web",
    "intensity": 60,
    "original": "In today's fast-paced digital landscape...",
    "result": "Right now, businesses that want to grow need a plan...",
    "qualityScore": 0.81,
    "changeRatio": 0.19,
    "similarity": 0.82,
    "aiProbabilityBefore": 0.74,
    "aiProbabilityAfter": 0.28,
    "verdictBefore": "ai",
    "verdictAfter": "human",
    "changes": [ ... ],
    "metricsBefore": { ... },
    "metricsAfter": { ... }
}
```

A run summary (counts, averages, timing, library version) is saved to the key-value store
under the **SUMMARY** key.

## Local development

The Actor code lives in `text_humanize_actor/` and the library in `texthumanize/`.

```bash
pip install -r requirements.txt && pip install -e .
apify run          # reads input from storage/key_value_stores/default/INPUT.json
```

## Deploy

```bash
apify push         # builds the Actor on Apify using .actor/Dockerfile
```

`.actor/Dockerfile` installs the library straight from this repository, so the Actor runs
exactly the checked-out version of `texthumanize`.

Running this Actor is subject to the TextHumanize license terms (see `LICENSE` and
`COMMERCIAL.md` in the repository root).
