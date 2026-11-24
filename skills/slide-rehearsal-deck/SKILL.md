---
name: slide-rehearsal-deck
description: >-
  Turns an existing presentation slide deck (PDF or exported PPTX) and background
  notes into a slide-by-slide visual rehearsal manual: an offline interactive
  HTML cue deck (with speaker filter, keyboard focus mode, and countdown timer)
  plus a print-ready A4-landscape PDF featuring an optional story/context recap,
  original slide renders, presentation logic, pitfall guardrails, cue keywords,
  and paced spoken scripts. Use when the user is preparing for a group or solo
  presentation, wants to review the whole slide flow visually, or needs spoken
  scripts paired alongside original slides.
---

# Slide Rehearsal Deck

Build a complete, zero-dependency visual rehearsal manual from a user's finalized slide deck so speakers can practice directly against their actual slides without switching windows or losing track of facts.

## Prerequisites

Python 3 with `pypdfium2` and `Pillow` installed (`pip install pypdfium2 pillow`). Export to A4-landscape PDF additionally uses an installed Chrome, Chromium, or Edge binary (or `CHROME_PATH`); if none is found, the HTML manual is still generated and can be printed to PDF from any browser.

## Workflow

### 1. Audit the Slides & Source Material

1. Read every page of the target slide PDF (if the user only has `.pptx`, export or ask for a `.pdf` copy first so layout matches exactly).
2. Read any accompanying background documents, task sheets, rubric requirements, or raw evidence.
3. Identify and log **contradictions, chronology mismatches, outdated speaker notes, or unsupported claims** on specific slides so they can be surfaced as visible guardrail callouts rather than repeated during delivery.

### 2. Draft `deck.json`

Create a structured JSON file matching [references/schema.md](./references/schema.md):

- **`overview` (optional opening page)**: Ideal when the speaker needs to re-memorize a messy timeline or case background (e.g., 4–6 chronological timeline cards, a progression/metric strip, and speaker division summary with cross-slide warnings).
- **`slides[]` (one entry per original slide, exact page order)**:
  - `title` & `time`: Exact slide title and target speaking duration (e.g., `"45s"`).
  - `keywords`: 3–4 short cue-card pills for quick glance during delivery.
  - `logic`: Why this slide sits here and how it bridges the previous and next slides.
  - `guard` + `guard_level` (`"danger"` | `"warn"` | `"info"`): Factual boundaries, slide-vs-reality mismatches, or handoff reminders.
  - `script`: Natural spoken English (~125–135 wpm) or Chinese (~220–260 chars/min), marking vocal stress words with `**bold**`.
  - `source`: Exact evidence or citation anchor.

Set `timer_seconds` to the primary speaker's target budget (for example, `360` for 6 minutes) and set `"is_primary": true` on the slides owned by the active presenter.

### 3. Build the Visual HTML & A4-Landscape PDF

Run [scripts/build_deck.py](./scripts/build_deck.py):

```bash
python scripts/build_deck.py \
  --pdf path/to/slides.pdf \
  --data path/to/deck.json \
  --out-html path/to/rehearsal-manual.html \
  --out-pdf path/to/rehearsal-manual.pdf \
  --verify-dir path/to/verify_pngs
```

Use `--language` inside `deck.json` (`"en"` or `"zh"`) to control the UI labels and print headings. All slide images are converted to JPEG and embedded inline as base64 data URIs so the generated HTML works completely offline with zero external CDN dependencies.

### 4. Visually Inspect Before Delivering

1. Confirm the output PDF page count equals `(1 if overview else 0) + len(slides)` — never allow a slide card to spill onto an extra print page.
2. Open at least the opening overview page (if present), one dense warning slide, and two primary-speaker slides from `--verify-dir` to confirm sharp slide renders, clean margins, and zero text truncation or overlap.
3. If using this skill or publishing examples publicly, **never include real student IDs, private chats, personal credentials, or unredacted course files** — always replace with fictionalized sample data before committing.
