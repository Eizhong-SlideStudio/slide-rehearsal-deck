#!/usr/bin/env python3
"""Build an offline interactive HTML rehearsal manual and optional A4-landscape PDF
from a presentation PDF and a structured JSON script file.
"""

import argparse
import base64
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pypdfium2 as pdfium


I18N = {
    "en": {
        "brand_suffix": "Rehearsal Manual",
        "flt_all": "All Slides ({n})",
        "flt_primary": "{name}'s Part ({n})",
        "flt_mate": "Teammates ({n})",
        "focus_btn": "Focus Mode",
        "timer_label": "Timer",
        "start": "Start",
        "pause": "Pause",
        "resume": "Resume",
        "reset": "Reset",
        "done": "Done",
        "print_pdf": "Print / Save PDF",
        "prev_focus": "← Prev (Left Arrow)",
        "next_focus": "Next (Right Arrow) →",
        "page_prefix": "Page",
        "overview_opt": "00 · Overview & Story Recap",
        "primary_badge": "★ Primary · {speaker}",
        "mate_badge": "Co-presenter · {speaker}",
        "target_time": "Target: ",
        "words_unit": "words",
        "logic_label": "Slide Logic (Role & Transitions)",
        "guard_danger": "⚠ Critical Fix / Redline",
        "guard_warn": "⚠ Watchout / Transition Note",
        "guard_info": "📌 Evidence & Delivery Boundary",
        "cues_label": "Cue Card Keywords (Glance & Speak)",
        "script_primary": "Your Spoken Script",
        "script_mate": "Co-presenter Script ({speaker} · For Alignment)",
        "copy_btn": "Copy Script",
        "copied": "Copied",
        "source_prefix": "Sources & Anchors: ",
    },
    "zh": {
        "brand_suffix": "可视化演讲手册",
        "flt_all": "全部 {n} 页",
        "flt_primary": "{name} 主讲 ({n} 页)",
        "flt_mate": "队友 ({n} 页)",
        "focus_btn": "专注翻页排练",
        "timer_label": "排练计时",
        "start": "开始",
        "pause": "暂停",
        "resume": "继续",
        "reset": "重置",
        "done": "完成",
        "print_pdf": "打印 / 导出 PDF",
        "prev_focus": "← 上一页（左方向键）",
        "next_focus": "下一页（右方向键） →",
        "page_prefix": "第",
        "overview_opt": "00 · 故事复盘 & 全场逻辑总览",
        "primary_badge": "★ 主讲 · {speaker}",
        "mate_badge": "队友 · {speaker}",
        "target_time": "目标用时：",
        "words_unit": "words",
        "logic_label": "演讲逻辑（为什么放这页 & 前后怎么串）",
        "guard_danger": "⚠ 必改 / 避坑红线",
        "guard_warn": "⚠ 衔接 / 口径提醒",
        "guard_info": "📌 证据与表达边界",
        "cues_label": "脱稿关键词（扫一眼就开口）",
        "script_primary": "你的实战口语稿",
        "script_mate": "参考英文讲稿（{speaker} 主讲，供对稿顺场）",
        "copy_btn": "复制讲稿",
        "copied": "已复制",
        "source_prefix": "证据与来源锚点：",
    },
}


def md_bold_to_html(text: str) -> str:
    """Safely escape HTML and convert **bold** spans to <strong>."""
    escaped = html.escape(text or "")
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)


def render_pdf_slides_b64(pdf_path: str, scale: float, jpeg_quality: int) -> list[str]:
    doc = pdfium.PdfDocument(pdf_path)
    encoded: list[str] = []
    try:
        for i in range(len(doc)):
            page = doc[i]
            bmp = page.render(scale=scale)
            pil_img = bmp.to_pil().convert("RGB")
            buf = io.BytesIO()
            pil_img.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
            encoded.append(base64.b64encode(buf.getvalue()).decode("ascii"))
            page.close()
    finally:
        doc.close()
    return encoded


def find_browser_binary() -> str | None:
    env_path = os.environ.get("CHROME_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        shutil.which("microsoft-edge"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    return None


def export_pdf_chrome(browser: str, html_path: Path, pdf_path: Path) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path.resolve()}",
        html_path.resolve().as_uri(),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0 or not pdf_path.exists():
        raise RuntimeError(
            f"Headless browser PDF export failed (code {res.returncode}): {res.stderr.strip()}"
        )


def render_verification_pngs(pdf_path: Path, verify_dir: Path) -> int:
    verify_dir.mkdir(parents=True, exist_ok=True)
    doc = pdfium.PdfDocument(str(pdf_path))
    count = len(doc)
    try:
        for idx in range(count):
            page = doc[idx]
            img = page.render(scale=1.5).to_pil()
            img.save(verify_dir / f"page_{idx + 1:02d}.png")
            page.close()
    finally:
        doc.close()
    return count


def build_overview_html(data: dict, lang: dict) -> str:
    ov = data.get("overview")
    if not ov:
        return ""

    pills_html = "".join(
        f'<span class="meta-pill">{html.escape(p)}</span>'
        for p in data.get("meta_pills", [])
    )

    timeline_cards = []
    for item in ov.get("timeline", []):
        tone = item.get("tone", "default")
        cls = "story-card"
        if tone == "highlight":
            cls += " highlight"
        elif tone == "alert":
            cls += " alert"
        quote_html = (
            f'<p class="story-quote">{html.escape(item["quote"])}</p>'
            if item.get("quote")
            else ""
        )
        timeline_cards.append(
            f"""
            <article class="{cls}">
              <div class="story-card-head">
                <span class="story-stage">{html.escape(item.get("stage", ""))}</span>
                <span class="story-time">{html.escape(item.get("time", ""))}</span>
              </div>
              <p class="story-body">{md_bold_to_html(item.get("body", ""))}</p>
              {quote_html}
            </article>
            """
        )

    prog_html = ""
    prog_items = ov.get("progression", [])
    if prog_items:
        steps = []
        for idx, step in enumerate(prog_items):
            if idx > 0:
                steps.append("<span>→</span>")
            tone = step.get("tone", "default")
            cls = "price-step"
            if tone == "deal":
                cls += " deal"
            elif tone == "cash":
                cls += " cash"
            steps.append(f'<span class="{cls}">{html.escape(step.get("label", ""))}</span>')
        label = html.escape(ov.get("progression_label", ""))
        prog_html = (
            f'<div class="price-bar">'
            f'<span style="font-weight:800;color:var(--brown);">{label}</span>'
            f'{"".join(steps)}</div>'
        )

    speakers = ov.get("speakers", [])
    sp_cols = min(3, max(1, len(speakers)))
    sp_cards = []
    for sp in speakers:
        cls = "arc-card mine" if sp.get("is_primary") else "arc-card"
        warn_html = (
            f'<div class="arc-warn">{html.escape(sp["warn"])}</div>'
            if sp.get("warn")
            else ""
        )
        sp_cards.append(
            f"""
            <div class="{cls}">
              <div class="arc-title">{html.escape(sp.get("title", ""))}</div>
              <p class="arc-desc">{md_bold_to_html(sp.get("desc", ""))}</p>
              {warn_html}
            </div>
            """
        )

    timeline_sec = ""
    if timeline_cards:
        t_cols = 2 if len(timeline_cards) in (2, 4) else 3
        timeline_sec = (
            f'<h2 class="sec-kicker">{html.escape(ov.get("timeline_title", ""))}</h2>'
            f'<div class="story-grid" style="grid-template-columns:repeat({t_cols},minmax(0,1fr));">'
            f'{"".join(timeline_cards)}</div>'
        )

    speakers_sec = ""
    if sp_cards:
        speakers_sec = (
            f'<h2 class="sec-kicker">{html.escape(ov.get("speakers_title", ""))}</h2>'
            f'<div class="arc-grid" style="grid-template-columns:repeat({sp_cols},minmax(0,1fr));">'
            f'{"".join(sp_cards)}</div>'
        )

    return f"""
    <section id="page-0" class="sheet is-primary" data-role="intro">
      <div class="hero-top">
        <div>
          <h1 class="hero-title">{html.escape(ov.get("heading", data.get("title", "")))}</h1>
          <p class="hero-sub">{html.escape(data.get("subtitle", ""))}</p>
        </div>
        <div class="meta-pills">{pills_html}</div>
      </div>
      {timeline_sec}
      {prog_html}
      {speakers_sec}
    </section>
    """


def build_html_document(data: dict, b64_images: list[str]) -> str:
    lang_code = data.get("language", "en")
    t = I18N["zh"] if lang_code == "zh" else I18N["en"]
    slides = data["slides"]
    total_slides = len(slides)
    has_overview = bool(data.get("overview"))
    primary_name = data.get("primary_speaker") or next(
        (s["speaker"] for s in slides if s.get("is_primary")), "Primary"
    )
    primary_count = sum(1 for s in slides if s.get("is_primary"))
    mate_count = total_slides - primary_count
    timer_seconds = int(data.get("timer_seconds", 360))
    init_mm = f"{timer_seconds // 60:02d}:{timer_seconds % 60:02d}"

    jump_options = []
    if has_overview:
        jump_options.append(f'<option value="page-0">{html.escape(t["overview_opt"])}</option>')

    slide_cards = []
    for idx, s in enumerate(slides):
        n = int(s["num"])
        is_primary = bool(s.get("is_primary", True))
        role = "primary" if is_primary else "teammate"
        role_cls = "is-primary" if is_primary else "is-teammate"
        speaker = html.escape(s.get("speaker", primary_name))
        speaker_badge = (
            f'<span class="badge badge-primary">{t["primary_badge"].format(speaker=speaker)}</span>'
            if is_primary
            else f'<span class="badge badge-mate">{t["mate_badge"].format(speaker=speaker)}</span>'
        )
        beat_html = (
            f'<span class="beat-tag">{html.escape(s["beat"])}</span>'
            if s.get("beat")
            else ""
        )
        g_lvl = s.get("guard_level", "info")
        guard_cls = {"danger": "box-danger", "warn": "box-warn", "info": "box-info"}.get(
            g_lvl, "box-info"
        )
        guard_label = {
            "danger": t["guard_danger"],
            "warn": t["guard_warn"],
            "info": t["guard_info"],
        }.get(g_lvl, t["guard_info"])

        guard_block = ""
        if s.get("guard"):
            guard_block = f"""
              <div class="guard-box {guard_cls}">
                <div class="box-label">{html.escape(guard_label)}</div>
                <p>{html.escape(s["guard"])}</p>
              </div>
            """

        cues_html = "".join(
            f'<span class="cue-pill">{html.escape(k)}</span>'
            for k in s.get("keywords", [])
        )
        raw_script = s.get("script", "")
        wc = len(re.sub(r"\*\*(.+?)\*\*", r"\1", raw_script).split())
        script_title = (
            t["script_primary"]
            if is_primary
            else t["script_mate"].format(speaker=s.get("speaker", ""))
        )
        source_html = (
            f'<div class="source-foot">{html.escape(t["source_prefix"])}{html.escape(s["source"])}</div>'
            if s.get("source")
            else ""
        )
        jump_options.append(
            f'<option value="slide-{n}">S{n:02d} · {speaker} · {html.escape(s.get("title", ""))}</option>'
        )

        slide_cards.append(
            f"""
            <section id="slide-{n}" class="sheet slide-sheet {role_cls}" data-role="{role}" data-slide="{n}">
              <header class="slide-head">
                <div class="head-left">
                  <span class="slide-num">S{n} / {total_slides}</span>
                  {speaker_badge}
                  {beat_html}
                  <h2 class="slide-title">{html.escape(s.get("title", ""))}</h2>
                </div>
                <div class="head-right">
                  <span class="time-pill">⏱ {html.escape(t["target_time"])}<strong>{html.escape(s.get("time", ""))}</strong></span>
                  <span class="wc-pill">~{wc} {html.escape(t["words_unit"])}</span>
                </div>
              </header>

              <div class="slide-grid">
                <div class="col-left">
                  <div class="img-frame">
                    <img src="data:image/jpeg;base64,{b64_images[idx]}" alt="Slide {n}: {html.escape(s.get('title', ''))}" />
                  </div>
                  <div class="logic-box">
                    <div class="box-label">{html.escape(t["logic_label"])}</div>
                    <p>{html.escape(s.get("logic", ""))}</p>
                  </div>
                  {guard_block}
                </div>

                <div class="col-right">
                  <div class="cues-wrap">
                    <div class="box-label">{html.escape(t["cues_label"])}</div>
                    <div class="cues-row">{cues_html}</div>
                  </div>
                  <div class="script-box">
                    <div class="script-head">
                      <span class="box-label">{html.escape(script_title)}</span>
                      <button type="button" class="copy-btn no-print" onclick="copyScript(this)">{html.escape(t["copy_btn"])}</button>
                    </div>
                    <div class="script-body">{md_bold_to_html(raw_script)}</div>
                  </div>
                  {source_html}
                </div>
              </div>
            </section>
            """
        )

    filter_buttons = f'<button class="tb-btn active" id="flt-all" onclick="setFilter(\'all\')">{html.escape(t["flt_all"].format(n=total_slides))}</button>'
    if mate_count > 0 and primary_count > 0:
        filter_buttons += (
            f'<button class="tb-btn" id="flt-primary" onclick="setFilter(\'primary\')">{html.escape(t["flt_primary"].format(name=primary_name, n=primary_count))}</button>'
            f'<button class="tb-btn" id="flt-mate" onclick="setFilter(\'teammate\')">{html.escape(t["flt_mate"].format(n=mate_count))}</button>'
        )

    overview_html = build_overview_html(data, t)
    deck_title = html.escape(data.get("title", t["brand_suffix"]))

    return f"""<!DOCTYPE html>
<html lang="{html.escape(lang_code)}">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{deck_title}</title>
<style>
  :root {{
    --canvas: #F6F1E9;
    --paper: #FFFFFF;
    --ink: #2C1E10;
    --brown: #5A3918;
    --muted: #6E5B49;
    --border: #E5D9C7;
    --amber: #D97706;
    --amber-soft: #FEF3C7;
    --amber-pale: #FFFBEB;
    --mate-soft: #F3EFEA;
    --danger-bg: #FEF2F2;
    --danger-bd: #F87171;
    --danger-ink: #991B1B;
    --warn-bg: #FFF7ED;
    --warn-bd: #FB923C;
    --warn-ink: #9A3412;
    --info-bg: #F8FAFC;
    --info-bd: #CBD5E1;
    --info-ink: #334155;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{
    margin: 0;
    padding: 0;
    background: var(--canvas);
    color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
  }}
  .toolbar {{
    position: sticky;
    top: 0;
    z-index: 50;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 10px 18px;
    background: rgba(255, 255, 255, 0.96);
    backdrop-filter: blur(8px);
    border-bottom: 1px solid var(--border);
    box-shadow: 0 2px 8px rgba(90, 57, 24, 0.06);
  }}
  .tb-group {{ display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }}
  .tb-brand {{ font-weight: 700; font-size: 14px; color: var(--brown); margin-right: 4px; }}
  .tb-btn, .tb-select {{
    font-size: 12.5px;
    font-weight: 600;
    padding: 5px 10px;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: #FFFFFF;
    color: var(--ink);
    cursor: pointer;
    transition: all 0.15s ease;
  }}
  .tb-btn:hover {{ border-color: var(--amber); color: var(--brown); }}
  .tb-btn.active {{ background: var(--brown); color: #FFFFFF; border-color: var(--brown); }}
  .tb-btn.primary {{ background: var(--amber); color: #FFFFFF; border-color: var(--amber); }}
  .timer-box {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 8px;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: var(--amber-pale);
    font-size: 12.5px;
  }}
  .timer-readout {{
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-weight: 700;
    font-size: 13.5px;
    color: var(--brown);
  }}
  .timer-readout.urgent {{ color: #DC2626; }}
  .deck-wrap {{
    max-width: 1140px;
    margin: 18px auto 40px;
    padding: 0 14px;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }}
  .sheet {{
    background: var(--paper);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 22px 26px;
    box-shadow: 0 4px 18px rgba(90, 57, 24, 0.06);
  }}
  .sheet.is-primary {{ border-top: 4px solid var(--amber); }}
  .sheet.is-teammate {{ border-top: 4px solid #C8B6A2; }}
  .sheet.hidden-by-filter {{ display: none !important; }}
  .focus-nav {{
    display: none;
    justify-content: space-between;
    align-items: center;
    padding: 8px 14px;
    background: var(--paper);
    border: 1px solid var(--border);
    border-radius: 10px;
    font-size: 13px;
  }}
  body.focus-mode .focus-nav {{ display: flex; }}
  .hero-top {{
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: flex-end;
    gap: 10px;
    padding-bottom: 10px;
    border-bottom: 2px solid var(--amber);
    margin-bottom: 12px;
  }}
  .hero-title {{ margin: 0; font-size: 21px; font-weight: 800; color: var(--brown); }}
  .hero-sub {{ margin: 2px 0 0; font-size: 12.5px; color: var(--muted); }}
  .meta-pills {{ display: flex; flex-wrap: wrap; gap: 6px; }}
  .meta-pill {{
    font-size: 11.5px;
    font-weight: 600;
    padding: 3px 9px;
    border-radius: 999px;
    background: var(--amber-pale);
    border: 1px solid #FDE68A;
    color: var(--brown);
  }}
  .sec-kicker {{ font-size: 13px; font-weight: 800; color: var(--brown); margin: 0 0 7px; }}
  .story-grid {{ display: grid; gap: 9px; margin-bottom: 10px; }}
  .story-card {{ border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; background: #FFFEFC; }}
  .story-card.highlight {{ background: var(--amber-pale); border-color: #FCD34D; }}
  .story-card.alert {{ background: #FFF9F9; border-color: #FECACA; }}
  .story-card-head {{ display: flex; justify-content: space-between; align-items: center; gap: 6px; margin-bottom: 4px; }}
  .story-stage {{ font-size: 12px; font-weight: 800; color: var(--brown); }}
  .story-time {{
    font-size: 10.5px;
    font-weight: 700;
    color: var(--muted);
    background: var(--mate-soft);
    padding: 1px 6px;
    border-radius: 4px;
    white-space: nowrap;
  }}
  .story-body {{ margin: 0; font-size: 11.5px; line-height: 1.44; color: var(--ink); }}
  .story-quote {{ margin: 4px 0 0; padding-top: 4px; border-top: 1px dashed var(--border); font-size: 10.8px; color: var(--muted); }}
  .price-bar {{
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    background: var(--mate-soft);
    border: 1px solid var(--border);
    border-radius: 7px;
    font-size: 11.5px;
    margin-bottom: 10px;
  }}
  .price-step {{ font-weight: 700; padding: 2px 7px; border-radius: 4px; background: #FFFFFF; border: 1px solid var(--border); }}
  .price-step.deal {{ background: var(--amber-soft); border-color: #F59E0B; color: #92400E; }}
  .price-step.cash {{ background: var(--danger-bg); border-color: var(--danger-bd); color: var(--danger-ink); }}
  .arc-grid {{ display: grid; gap: 9px; }}
  .arc-card {{ border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; background: #FFFFFF; }}
  .arc-card.mine {{ background: var(--amber-pale); border-color: var(--amber); }}
  .arc-title {{ font-size: 12px; font-weight: 800; color: var(--brown); margin-bottom: 3px; }}
  .arc-desc {{ font-size: 11.4px; line-height: 1.44; color: var(--ink); margin: 0; }}
  .arc-warn {{ margin-top: 4px; font-size: 10.8px; font-weight: 700; color: var(--danger-ink); }}
  .slide-head {{
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    padding-bottom: 9px;
    margin-bottom: 12px;
    border-bottom: 1px solid var(--border);
  }}
  .head-left {{ display: flex; flex-wrap: wrap; align-items: center; gap: 7px; min-width: 0; }}
  .slide-num {{ font-size: 12px; font-weight: 800; padding: 2px 8px; border-radius: 6px; background: var(--brown); color: #FFFFFF; }}
  .badge {{ font-size: 11.5px; font-weight: 700; padding: 2px 8px; border-radius: 6px; }}
  .badge-primary {{ background: var(--amber); color: #FFFFFF; }}
  .badge-mate {{ background: var(--mate-soft); color: var(--brown); border: 1px solid var(--border); }}
  .beat-tag {{
    font-size: 11.5px;
    font-weight: 600;
    color: var(--muted);
    background: #FAF7F2;
    border: 1px solid var(--border);
    padding: 2px 7px;
    border-radius: 6px;
  }}
  .slide-title {{ margin: 0; font-size: 16px; font-weight: 800; color: var(--brown); }}
  .head-right {{ display: flex; align-items: center; gap: 8px; }}
  .time-pill {{
    font-size: 12px;
    padding: 3px 9px;
    border-radius: 999px;
    background: var(--amber-pale);
    border: 1px solid #FCD34D;
    color: var(--brown);
  }}
  .wc-pill {{ font-size: 11.5px; color: var(--muted); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
  .slide-grid {{ display: grid; grid-template-columns: 1.15fr 0.95fr; gap: 16px; align-items: stretch; }}
  .col-left {{ display: flex; flex-direction: column; gap: 9px; }}
  .col-right {{ display: flex; flex-direction: column; gap: 10px; }}
  .img-frame {{
    width: 100%;
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid var(--border);
    background: #FFFFFF;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
  }}
  .img-frame img {{ display: block; width: 100%; height: auto; aspect-ratio: 16 / 9; object-fit: contain; }}
  .box-label {{ font-size: 11.5px; font-weight: 800; color: var(--brown); margin-bottom: 3px; }}
  .logic-box {{ border: 1px solid var(--border); border-radius: 8px; padding: 8px 11px; background: #FFFDF9; }}
  .logic-box p, .guard-box p {{ margin: 0; font-size: 12.2px; line-height: 1.46; }}
  .guard-box {{ border-radius: 8px; padding: 8px 11px; border: 1px solid var(--info-bd); }}
  .box-danger {{ background: var(--danger-bg); border-color: var(--danger-bd); color: var(--danger-ink); }}
  .box-danger .box-label {{ color: var(--danger-ink); }}
  .box-warn {{ background: var(--warn-bg); border-color: var(--warn-bd); color: var(--warn-ink); }}
  .box-warn .box-label {{ color: var(--warn-ink); }}
  .box-info {{ background: var(--info-bg); border-color: var(--info-bd); color: var(--info-ink); }}
  .box-info .box-label {{ color: var(--info-ink); }}
  .cues-wrap {{ border: 1px solid var(--border); border-radius: 8px; padding: 8px 11px; background: #FFFEFC; }}
  .cues-row {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }}
  .cue-pill {{
    font-size: 12px;
    font-weight: 700;
    padding: 3px 9px;
    border-radius: 6px;
    background: var(--amber-soft);
    border: 1px solid #FCD34D;
    color: #78350F;
  }}
  .is-teammate .cue-pill {{ background: var(--mate-soft); border-color: var(--border); color: var(--brown); }}
  .script-box {{
    flex: 1;
    display: flex;
    flex-direction: column;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px 13px;
    background: #FFFFFF;
  }}
  .is-primary .script-box {{ border-color: #F59E0B; background: #FFFEFA; }}
  .script-head {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
    padding-bottom: 5px;
    border-bottom: 1px dashed var(--border);
  }}
  .copy-btn {{
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 5px;
    border: 1px solid var(--border);
    background: #FAF7F2;
    color: var(--brown);
    cursor: pointer;
  }}
  .copy-btn:hover {{ background: var(--amber-soft); }}
  .script-body {{ font-size: 13.5px; line-height: 1.56; color: #1F160D; }}
  .script-body strong {{
    color: #9A3412;
    background: rgba(254, 243, 199, 0.55);
    padding: 0 2px;
    border-radius: 3px;
  }}
  .source-foot {{ font-size: 11px; color: var(--muted); padding: 0 2px; }}

  @media screen and (max-width: 900px) {{
    .story-grid, .arc-grid, .slide-grid {{ grid-template-columns: 1fr !important; }}
  }}
  @media print {{
    @page {{ size: 297mm 210mm; margin: 0; }}
    html, body {{ background: #FFFFFF !important; margin: 0 !important; padding: 0 !important; }}
    .no-print {{ display: none !important; }}
    .deck-wrap {{ max-width: none !important; width: 297mm !important; margin: 0 !important; padding: 0 !important; gap: 0 !important; display: block !important; }}
    .sheet {{
      display: block !important;
      width: 297mm !important;
      height: 210mm !important;
      padding: 8mm 10mm !important;
      margin: 0 !important;
      border: none !important;
      border-radius: 0 !important;
      box-shadow: none !important;
      overflow: hidden !important;
      page-break-after: always;
      break-after: page;
    }}
    .sheet:last-of-type {{ page-break-after: auto; break-after: auto; }}
    .sheet.is-primary {{ border-top: 4px solid var(--amber) !important; }}
    .sheet.is-teammate {{ border-top: 4px solid #C8B6A2 !important; }}
    .slide-grid {{ grid-template-columns: 1.15fr 0.95fr !important; gap: 14px !important; }}
    .img-frame img {{ max-height: 92mm !important; }}
    .script-body {{ font-size: 13px !important; line-height: 1.52 !important; }}
  }}
</style>
</head>
<body>
  <nav class="toolbar no-print">
    <div class="tb-group">
      <span class="tb-brand">{deck_title}</span>
      {filter_buttons}
      <button class="tb-btn" id="btn-focus" onclick="toggleFocus()">{html.escape(t["focus_btn"])}</button>
      <select class="tb-select" id="jump-sel" onchange="jumpTo(this.value)">
        {''.join(jump_options)}
      </select>
    </div>
    <div class="tb-group">
      <div class="timer-box">
        <span>{html.escape(t["timer_label"])}</span>
        <span class="timer-readout" id="timer-readout">{init_mm}</span>
        <button class="tb-btn" id="timer-btn" onclick="toggleTimer()">{html.escape(t["start"])}</button>
        <button class="tb-btn" onclick="resetTimer()">{html.escape(t["reset"])}</button>
      </div>
      <button class="tb-btn primary" onclick="window.print()">{html.escape(t["print_pdf"])}</button>
    </div>
  </nav>

  <main class="deck-wrap" id="deck-wrap">
    <div class="focus-nav no-print" id="focus-nav">
      <button class="tb-btn" onclick="moveFocus(-1)">{html.escape(t["prev_focus"])}</button>
      <span id="focus-indicator" style="font-weight:700;color:var(--brown);"></span>
      <button class="tb-btn" onclick="moveFocus(1)">{html.escape(t["next_focus"])}</button>
    </div>
    {overview_html}
    {''.join(slide_cards)}
  </main>

  <script>
    const TXT = {json.dumps({
        "start": t["start"],
        "pause": t["pause"],
        "resume": t["resume"],
        "done": t["done"],
        "copied": t["copied"],
        "copy_btn": t["copy_btn"],
        "page_prefix": t["page_prefix"],
        "lang": lang_code,
    })};
    const PRESET_SEC = {timer_seconds};
    let currentFilter = 'all';
    let focusMode = false;
    let focusIndex = 0;
    let timerSec = PRESET_SEC;
    let timerId = null;

    function getVisibleSheets() {{
      return Array.from(document.querySelectorAll('.sheet')).filter(el => {{
        if (currentFilter === 'all') return true;
        if (currentFilter === 'primary') return el.dataset.role === 'intro' || el.dataset.role === 'primary';
        if (currentFilter === 'teammate') return el.dataset.role === 'intro' || el.dataset.role === 'teammate';
        return true;
      }});
    }}

    function applyVisibility() {{
      const allSheets = Array.from(document.querySelectorAll('.sheet'));
      const vis = getVisibleSheets();
      if (focusIndex >= vis.length) focusIndex = Math.max(0, vis.length - 1);
      allSheets.forEach(el => el.classList.add('hidden-by-filter'));
      if (focusMode) {{
        if (vis[focusIndex]) {{
          vis[focusIndex].classList.remove('hidden-by-filter');
          const tag = vis[focusIndex].id === 'page-0' ? 'Overview' : 'Slide ' + vis[focusIndex].dataset.slide;
          const label = TXT.lang === 'zh'
            ? `第 ${{focusIndex + 1}} / ${{vis.length}} 屏 · ${{tag}}`
            : `Page ${{focusIndex + 1}} / ${{vis.length}} · ${{tag}}`;
          document.getElementById('focus-indicator').textContent = label;
        }}
      }} else {{
        vis.forEach(el => el.classList.remove('hidden-by-filter'));
      }}
    }}

    function setFilter(mode) {{
      currentFilter = mode;
      focusIndex = 0;
      const bAll = document.getElementById('flt-all');
      const bPri = document.getElementById('flt-primary');
      const bMat = document.getElementById('flt-mate');
      if (bAll) bAll.classList.toggle('active', mode === 'all');
      if (bPri) bPri.classList.toggle('active', mode === 'primary');
      if (bMat) bMat.classList.toggle('active', mode === 'teammate');
      applyVisibility();
    }}

    function toggleFocus() {{
      focusMode = !focusMode;
      document.body.classList.toggle('focus-mode', focusMode);
      document.getElementById('btn-focus').classList.toggle('active', focusMode);
      focusIndex = 0;
      applyVisibility();
    }}

    function moveFocus(delta) {{
      if (!focusMode) return;
      const vis = getVisibleSheets();
      if (!vis.length) return;
      focusIndex = (focusIndex + delta + vis.length) % vis.length;
      applyVisibility();
      window.scrollTo({{ top: 0, behavior: 'smooth' }});
    }}

    function jumpTo(id) {{
      const target = document.getElementById(id);
      if (!target) return;
      if (target.classList.contains('hidden-by-filter') && !focusMode) setFilter('all');
      if (focusMode) {{
        let vis = getVisibleSheets();
        let idx = vis.findIndex(el => el.id === id);
        if (idx < 0) {{
          setFilter('all');
          vis = getVisibleSheets();
          idx = Math.max(0, vis.findIndex(el => el.id === id));
        }}
        focusIndex = idx;
        applyVisibility();
        window.scrollTo({{ top: 0, behavior: 'smooth' }});
      }} else {{
        target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
      }}
    }}

    function copyScript(btn) {{
      const txt = btn.closest('.script-box').querySelector('.script-body').innerText;
      navigator.clipboard?.writeText(txt).then(() => {{
        btn.textContent = TXT.copied;
        setTimeout(() => btn.textContent = TXT.copy_btn, 1200);
      }});
    }}

    function renderTimer() {{
      const m = String(Math.floor(timerSec / 60)).padStart(2, '0');
      const s = String(timerSec % 60).padStart(2, '0');
      const el = document.getElementById('timer-readout');
      el.textContent = `${{m}}:${{s}}`;
      el.classList.toggle('urgent', timerSec <= 30);
    }}

    function toggleTimer() {{
      const btn = document.getElementById('timer-btn');
      if (timerId) {{
        clearInterval(timerId);
        timerId = null;
        btn.textContent = TXT.resume;
      }} else {{
        if (timerSec === 0) timerSec = PRESET_SEC;
        btn.textContent = TXT.pause;
        timerId = setInterval(() => {{
          if (timerSec > 0) {{
            timerSec--;
            renderTimer();
          }} else {{
            clearInterval(timerId);
            timerId = null;
            btn.textContent = TXT.done;
          }}
        }}, 1000);
      }}
    }}

    function resetTimer() {{
      if (timerId) {{
        clearInterval(timerId);
        timerId = null;
      }}
      timerSec = PRESET_SEC;
      document.getElementById('timer-btn').textContent = TXT.start;
      renderTimer();
    }}

    document.addEventListener('keydown', (e) => {{
      if (!focusMode) return;
      if (e.key === 'ArrowRight') moveFocus(1);
      if (e.key === 'ArrowLeft') moveFocus(-1);
    }});

    applyVisibility();
    renderTimer();
  </script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build an offline visual presentation rehearsal manual (HTML + A4-landscape PDF)."
    )
    parser.add_argument("--pdf", required=True, help="Path to original slides PDF.")
    parser.add_argument("--data", required=True, help="Path to deck.json metadata and scripts.")
    parser.add_argument("--out-html", required=True, help="Output path for standalone HTML.")
    parser.add_argument("--out-pdf", help="Optional output path for A4-landscape PDF.")
    parser.add_argument("--verify-dir", help="Optional directory to dump PNG checks of the generated PDF.")
    parser.add_argument("--scale", type=float, default=2.0, help="Slide PDF render scale (default: 2.0).")
    parser.add_argument("--jpeg-quality", type=int, default=86, help="Embedded JPEG quality (default: 86).")
    args = parser.parse_args()

    with open(args.data, encoding="utf-8") as f:
        data = json.load(f)

    slides = data.get("slides", [])
    b64_images = render_pdf_slides_b64(args.pdf, args.scale, args.jpeg_quality)
    if len(b64_images) != len(slides):
        raise ValueError(
            f"Slide count mismatch: PDF has {len(b64_images)} pages, JSON defines {len(slides)} slides."
        )

    out_html = Path(args.out_html)
    out_html.parent.mkdir(parents=True, exist_ok=True)
    html_text = build_html_document(data, b64_images)
    out_html.write_text(html_text, encoding="utf-8")
    print(f"HTML written: {out_html} ({len(html_text):,} bytes, {len(slides)} slides)")

    if args.out_pdf:
        out_pdf = Path(args.out_pdf)
        browser = find_browser_binary()
        if not browser:
            print(
                "Warning: Chrome/Chromium/Edge not found; skipped PDF export. "
                "Set CHROME_PATH or print from a browser.",
                file=sys.stderr,
            )
            return 0
        export_pdf_chrome(browser, out_html, out_pdf)
        doc = pdfium.PdfDocument(str(out_pdf))
        expected = (1 if data.get("overview") else 0) + len(slides)
        actual = len(doc)
        doc.close()
        print(f"PDF written: {out_pdf} ({out_pdf.stat().st_size:,} bytes, {actual} pages; expected {expected})")
        if actual != expected:
            print(
                f"Warning: PDF page count ({actual}) differs from expected ({expected}); tighten text length.",
                file=sys.stderr,
            )
        if args.verify_dir:
            count = render_verification_pngs(out_pdf, Path(args.verify_dir))
            print(f"Verification PNGs written: {count} files in {args.verify_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
