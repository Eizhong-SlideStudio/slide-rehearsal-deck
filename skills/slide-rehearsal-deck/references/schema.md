# `deck.json` Schema & Pacing Reference

This schema drives [`scripts/build_deck.py`](../scripts/build_deck.py). All strings support plain text; `script` and `overview.timeline[].body` additionally render `**bold**` markers as highlighted emphasis (`<strong>`) after HTML escaping.

## Top-Level Object

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `title` | string | Yes | Manual title shown in the browser `<title>` and top toolbar. |
| `subtitle` | string | No | Short subtitle shown on the opening overview page. |
| `language` | `"en"` \| `"zh"` | No | Controls UI labels (`"en"` default). |
| `primary_speaker` | string | No | Name of the active user for filter labels and badges. |
| `timer_seconds` | integer | No | Countdown timer preset in seconds (default `360`). |
| `meta_pills` | string[] | No | Up to 5 metadata badges on the overview header (date, room, order, total duration). |
| `overview` | object | No | Optional opening recap page (Page 0). Omit to generate slide pages only. |
| `slides` | object[] | Yes | Ordered array matching every page `1..N` of `--pdf`. |

## `overview` Object (Optional)

| Field | Type | Description |
| :--- | :--- | :--- |
| `heading` | string | Main heading for Page 0 (e.g., `"Pilot Story Recap & Full 4-Slide Map"`). |
| `timeline_title` | string | Section title above the story/context grid. |
| `timeline` | object[] | 3 to 6 cards (`3×2` print grid). Fields: `stage`, `time`, `body`, `quote` (optional), `tone` (`"default"` \| `"alert"` \| `"highlight"`). |
| `progression_label` | string | Label for the horizontal progression strip (e.g., `"Price / Adoption Track:"`). |
| `progression` | object[] | Sequence of pill steps. Fields: `label`, `tone` (`"default"` \| `"deal"` \| `"cash"`). |
| `speakers_title` | string | Section title above the speaker division cards. |
| `speakers` | object[] | 1 to 3 cards (`repeat(3, 1fr)` on 3 speakers, auto-grid otherwise). Fields: `title`, `desc`, `warn` (optional), `is_primary` (boolean). |

## `slides[]` Item

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `num` | integer | Yes | 1-based page number matching the PDF page (`1..N`). |
| `speaker` | string | Yes | Speaker name shown in the top badge. |
| `is_primary` | boolean | Yes | `true` highlights the card in warm amber and groups it under the primary-speaker filter. |
| `beat` | string | No | Narrative section tag (e.g., `"Part B · Core Mechanism"`). |
| `title` | string | Yes | Exact title from the slide. |
| `time` | string | Yes | Target duration label (e.g., `"45s"`). |
| `keywords` | string[] | Yes | 3–4 short cue pills for glanceable delivery. |
| `logic` | string | Yes | Why this slide appears here and how it connects before/after. |
| `guard` | string | No | Factual boundary, contradiction warning, or delivery reminder. |
| `guard_level` | `"danger"` \| `"warn"` \| `"info"` | No | Visual severity styling (`"info"` default). |
| `script` | string | Yes | Spoken script (`**word**` highlights vocal stress). |
| `source` | string | No | Evidence, slide number, or citation anchor printed under the script box. |

## Speaking Pace Guidelines (Keep Print Pages Clean)

- **English delivery**: target **125–135 words per minute** (~2.1–2.25 words/sec). A 45-second slide holds ~90–100 words cleanly on a single A4 landscape page.
- **Chinese delivery**: target **220–260 characters per minute**.
- **Print budget check**: keep `logic` + `guard` concise (~2–4 sentences combined) and `script` under ~165 words per slide so every sheet fits inside `297mm × 210mm` without clipping.
