"""
app.py

Gradio interface for FitFindr.

Run with:
    python app.py

Then open the localhost URL shown in your terminal (usually http://localhost:7860).
"""

import re
import gradio as gr

from agent import run_agent
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe
import html as _html


# ── Gradio base theme ─────────────────────────────────────────────────────────

_theme = gr.themes.Base(
    primary_hue=gr.themes.colors.amber,
    neutral_hue=gr.themes.colors.zinc,
    font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "sans-serif"],
).set(
    body_background_fill="#0A0A0A",
    body_text_color="#F0EDE8",
    background_fill_primary="#111111",
    background_fill_secondary="#1A1A1A",
    border_color_primary="rgba(255,255,255,0.08)",
    button_primary_background_fill="#F4A261",
    button_primary_background_fill_hover="#E8935A",
    button_primary_text_color="#0A0A0A",
    button_primary_border_color="transparent",
    input_background_fill="#1A1A1A",
    input_border_color="rgba(255,255,255,0.08)",
    input_border_color_focus="rgba(244,162,97,0.45)",
    input_placeholder_color="#555555",
    block_background_fill="#111111",
    block_border_color="rgba(255,255,255,0.07)",
    panel_background_fill="#0A0A0A",
    checkbox_background_color="#1A1A1A",
    checkbox_background_color_selected="#F4A261",
    checkbox_label_background_fill="#1A1A1A",
    checkbox_label_background_fill_hover="#222222",
    checkbox_label_text_color="#8C8C8C",
    checkbox_label_text_color_selected="#F4A261",
)

# ── CSS ───────────────────────────────────────────────────────────────────────

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:ital,wght@0,400;0,500;0,700;1,400;1,500&display=swap');

body, .gradio-container { background: #0A0A0A !important; transition: background 0.3s !important; }
footer { display: none !important; }

@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { transition: none !important; animation: none !important; }
}

/* ── theme toggle (fixed top-right pill) ── */
#ff-theme-btn {
    position: fixed !important;
    top: 18px !important;
    right: 22px !important;
    z-index: 9999 !important;
    width: auto !important;
}
#ff-theme-btn button {
    font-size: 0 !important;        /* hide Gradio's static text */
    padding: 7px 18px !important;
    border-radius: 100px !important;
    background: #1E1E1E !important;
    border: 1px solid rgba(255,255,255,0.09) !important;
    box-shadow: 0 2px 10px rgba(0,0,0,0.4) !important;
    transition: background 0.18s, border-color 0.18s !important;
    height: auto !important;
    min-height: unset !important;
    cursor: pointer !important;
}
/* CSS-driven label — avoids Gradio state complexity */
#ff-theme-btn button::after {
    content: 'Switch to Light  \2600';   /* ☀ dark mode label */
    font-family: 'Inter', sans-serif !important;
    font-size: 0.7rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.05em !important;
    color: #888888 !important;
}
body.ff-light #ff-theme-btn button::after {
    content: 'Switch to Dark  \263E';    /* ☾ light mode label */
}
#ff-theme-btn button:hover {
    background: #252525 !important;
    border-color: rgba(255,255,255,0.14) !important;
}
#ff-theme-btn button:hover::after { color: #F0EDE8 !important; }
body.ff-light #ff-theme-btn button:hover::after { color: #1C1C1A !important; }

/* ── hero ── */
.ff-hero { text-align: center; padding: 60px 0 6px; }
.ff-logo {
    display: block;
    font-family: 'Playfair Display', serif;
    font-size: 3.75rem;
    font-weight: 700;
    font-style: italic;
    letter-spacing: -0.02em;
    line-height: 1;
    color: #F0EDE8;
    transition: color 0.3s;
}
.ff-accent {
    font-style: normal;
    color: #F4A261;
    transition: color 0.3s;
}
.ff-tagline {
    display: block;
    margin-top: 12px;
    font-family: 'Inter', sans-serif;
    font-size: 0.75rem;
    color: #2A2A2A;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    font-weight: 500;
    transition: color 0.3s;
}

/* ── search card ── */
#ff-search {
    background: #111111 !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 20px !important;
    padding: 20px !important;
    margin: 28px 0 14px !important;
    transition: background 0.3s, border-color 0.3s !important;
}
#ff-query label > span {
    font-family: 'Inter', sans-serif !important;
    font-size: 0.68rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
}
#ff-query textarea {
    font-family: 'Inter', sans-serif !important;
    background: #1A1A1A !important;
    color: #F0EDE8 !important;
    border-radius: 12px !important;
    font-size: 0.9375rem !important;
    line-height: 1.65 !important;
    resize: none !important;
    transition: background 0.3s, color 0.3s, border-color 0.2s, box-shadow 0.2s !important;
}
#ff-query textarea:focus { box-shadow: 0 0 0 3px rgba(244,162,97,0.08) !important; }
#ff-query textarea::placeholder { color: #555555 !important; opacity: 1 !important; }
#ff-wardrobe label > span:first-child {
    font-family: 'Inter', sans-serif !important;
    font-size: 0.68rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
}
#ff-wardrobe .wrap { gap: 8px !important; }

/* wardrobe helper text */
.wardrobe-info {
    font-family: 'Inter', sans-serif;
    font-size: 0.75rem;
    color: #444444;
    margin: 4px 0 0 2px;
    line-height: 1.55;
    transition: color 0.3s;
}

/* ── submit button ── */
#ff-submit button {
    font-family: 'Inter', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.875rem !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    border-radius: 12px !important;
    height: 52px !important;
    background: #F4A261 !important;
    color: #0A0A0A !important;
    border: none !important;
    transition: background 0.2s, transform 0.2s, box-shadow 0.2s !important;
    cursor: pointer !important;
}
#ff-submit button:hover {
    background: #E8935A !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 10px 28px rgba(244,162,97,0.22) !important;
}
#ff-submit button:active { transform: translateY(0) !important; }

/* ── output cards ── */
.output-card {
    background: #111111 !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 20px !important;
    min-height: 320px !important;
    display: flex !important;
    flex-direction: column !important;
    transition: background 0.3s, border-color 0.3s, box-shadow 0.3s !important;
}
.card-label {
    font-family: 'Inter', sans-serif;
    font-size: 0.63rem;
    font-weight: 700;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: #3A3A3A;
    padding: 18px 20px 0;
    display: block;
    transition: color 0.3s;
}

/* listing + fitcard markdown */
#ff-listing, #ff-fitcard {
    background: transparent !important;
    border: none !important;
    padding: 10px 20px 20px !important;
}
#ff-listing .prose, #ff-fitcard .prose {
    font-family: 'Inter', sans-serif !important;
    color: #9A9A94 !important;
    font-size: 0.9rem !important;
    line-height: 1.78 !important;
    transition: color 0.3s !important;
}
#ff-listing .prose h3, #ff-fitcard .prose h3 {
    font-family: 'Playfair Display', serif !important;
    font-size: 1.15rem !important;
    font-weight: 700 !important;
    font-style: italic !important;
    color: #EDEAE4 !important;
    margin: 4px 0 8px !important;
    line-height: 1.3 !important;
    transition: color 0.3s !important;
}
#ff-listing .prose strong, #ff-fitcard .prose strong { color: #F4A261 !important; font-weight: 600 !important; }
#ff-listing .prose hr, #ff-fitcard .prose hr {
    border: none !important;
    border-top: 1px solid rgba(255,255,255,0.06) !important;
    margin: 10px 0 !important;
    transition: border-color 0.3s !important;
}
#ff-listing .prose em { font-style: normal !important; color: #3A3A3A !important; font-size: 0.78rem !important; }
#ff-listing .prose p { margin-bottom: 5px !important; }
/* style tags as amber chips */
#ff-listing .prose code {
    background: rgba(244,162,97,0.08) !important;
    border: 1px solid rgba(244,162,97,0.14) !important;
    color: #C4824A !important;
    border-radius: 5px !important;
    padding: 2px 7px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.72rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.03em !important;
}
#ff-fitcard .prose { padding-left: 14px !important; border-left: 2px solid rgba(244,162,97,0.18) !important; }
#ff-fitcard .prose p {
    color: #8A8A84 !important;
    font-style: italic !important;
    font-size: 0.9rem !important;
    line-height: 1.85 !important;
    margin-bottom: 8px !important;
}

/* ── outfit HTML panel ── */
#ff-outfit { background: transparent !important; border: none !important; padding: 8px 14px 16px !important; }
.outfit-container { display: flex; flex-direction: column; gap: 8px; }
.outfit-intro {
    font-family: 'Inter', sans-serif;
    color: #555555;
    font-size: 0.855rem;
    line-height: 1.65;
    margin: 0;
    padding: 0 4px 2px;
    transition: color 0.3s;
}
.outfit-options { display: flex; flex-direction: column; gap: 5px; }
.outfit-accordion {
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 12px;
    overflow: hidden;
    transition: border-color 0.2s, box-shadow 0.2s;
}
.outfit-accordion[open] { border-color: rgba(244,162,97,0.22); box-shadow: 0 4px 18px rgba(0,0,0,0.35); }
.outfit-summary {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 13px 14px;
    cursor: pointer;
    background: #181818;
    list-style: none;
    user-select: none;
    transition: background 0.15s;
}
.outfit-summary::-webkit-details-marker { display: none; }
.outfit-summary:hover { background: #1E1E1E; }
.outfit-label {
    font-family: 'Inter', sans-serif;
    font-weight: 700;
    font-size: 0.65rem;
    color: #F4A261;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    white-space: nowrap;
    flex-shrink: 0;
    min-width: 52px;
    transition: color 0.3s;
}
.outfit-preview {
    font-family: 'Inter', sans-serif;
    font-size: 0.855rem;
    color: #555555;
    line-height: 1.4;
    flex: 1;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    transition: color 0.3s;
}
details[open] .outfit-preview { white-space: normal; color: #888884; }
.outfit-chevron { color: #3A3A3A; font-size: 0.6rem; flex-shrink: 0; transition: transform 0.2s, color 0.2s; }
details[open] .outfit-chevron { transform: rotate(180deg); color: #F4A261; }

/* accordion content — steps layout */
.outfit-content {
    padding: 14px 16px 16px;
    background: #131313;
    border-top: 1px solid rgba(255,255,255,0.05);
    transition: background 0.3s;
}

/* numbered steps list */
.outfit-steps {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 9px;
    counter-reset: step;
}
.outfit-step {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    counter-increment: step;
}
.outfit-step::before {
    content: counter(step);
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 22px;
    height: 22px;
    background: rgba(244,162,97,0.1);
    border: 1px solid rgba(244,162,97,0.16);
    border-radius: 50%;
    font-family: 'Inter', sans-serif;
    font-size: 0.62rem;
    font-weight: 700;
    color: #F4A261;
    margin-top: 2px;
    flex-shrink: 0;
    transition: background 0.3s, border-color 0.3s, color 0.3s;
}
.outfit-step-text {
    font-family: 'Inter', sans-serif;
    font-size: 0.875rem;
    color: #8A8A84;
    line-height: 1.65;
    transition: color 0.3s;
}
.outfit-step-solo {
    font-family: 'Inter', sans-serif;
    font-size: 0.875rem;
    color: #8A8A84;
    line-height: 1.75;
    margin: 0;
}
.outfit-closing {
    font-family: 'Inter', sans-serif;
    color: #333333;
    font-size: 0.8rem;
    line-height: 1.6;
    margin: 0;
    padding: 0 4px;
    font-style: italic;
    transition: color 0.3s;
}

/* ── examples table ── */
.gradio-container table {
    background: #0E0E0E !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 16px !important;
    border-collapse: separate !important;
    border-spacing: 0 !important;
    overflow: hidden !important;
    width: 100% !important;
    transition: background 0.3s, border-color 0.3s !important;
}
.gradio-container th {
    background: #141414 !important;
    color: #333333 !important;
    border-bottom: 1px solid rgba(255,255,255,0.05) !important;
    padding: 10px 18px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.63rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.14em !important;
    text-transform: uppercase !important;
    text-align: left !important;
    transition: background 0.3s, color 0.3s !important;
}
.gradio-container td {
    background: #0E0E0E !important;
    color: #444444 !important;
    border-bottom: 1px solid rgba(255,255,255,0.04) !important;
    padding: 11px 18px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.875rem !important;
    cursor: pointer !important;
    transition: background 0.12s, color 0.12s !important;
}
.gradio-container tr:last-child td { border-bottom: none !important; }
.gradio-container tr:hover td { background: #181818 !important; color: #E8E4DE !important; }
.gradio-container .label-wrap,
.gradio-container .label-wrap span {
    color: #333333 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.68rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
}


/* ============================================================
   LIGHT MODE  —  toggled by adding .ff-light to <body>
   ============================================================ */

body.ff-light,
body.ff-light .gradio-container { background: #F5F0E8 !important; }

/* theme button */
body.ff-light #ff-theme-btn button {
    background: #FFFFFF !important;
    border-color: rgba(0,0,0,0.10) !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.07) !important;
}
body.ff-light #ff-theme-btn button:hover {
    background: #F0ECE4 !important;
    border-color: rgba(0,0,0,0.14) !important;
}

/* hero */
body.ff-light .ff-logo   { color: #1C1C1A !important; }
body.ff-light .ff-accent { color: #C96522 !important; }
body.ff-light .ff-tagline { color: #BBBBBB !important; }

/* search card */
body.ff-light #ff-search {
    background: #EDE9E1 !important;
    border-color: rgba(0,0,0,0.06) !important;
}
body.ff-light #ff-query textarea {
    background: #FFFFFF !important;
    color: #1C1C1A !important;
    border-color: rgba(0,0,0,0.08) !important;
}
body.ff-light #ff-query textarea:focus {
    box-shadow: 0 0 0 3px rgba(201,101,34,0.08) !important;
}
body.ff-light #ff-query textarea::placeholder { color: #BBBBBB !important; }
body.ff-light #ff-query label > span { color: #AAAAAA !important; }
body.ff-light #ff-wardrobe label > span:first-child { color: #AAAAAA !important; }
body.ff-light .wardrobe-info { color: #AAAAAA !important; }

/* submit */
body.ff-light #ff-submit button {
    background: #C96522 !important;
    color: #FFFFFF !important;
}
body.ff-light #ff-submit button:hover {
    background: #A85218 !important;
    box-shadow: 0 8px 22px rgba(201,101,34,0.2) !important;
}

/* output cards */
body.ff-light .output-card {
    background: #FFFFFF !important;
    border-color: rgba(0,0,0,0.07) !important;
    box-shadow: 0 2px 14px rgba(0,0,0,0.05) !important;
}
body.ff-light .card-label { color: #AAAAAA !important; }

/* listing text */
body.ff-light #ff-listing .prose,
body.ff-light #ff-fitcard .prose { color: #5A5A56 !important; }
body.ff-light #ff-listing .prose h3,
body.ff-light #ff-fitcard .prose h3 { color: #1C1C1A !important; }
body.ff-light #ff-listing .prose strong,
body.ff-light #ff-fitcard .prose strong { color: #C96522 !important; }
body.ff-light #ff-listing .prose hr,
body.ff-light #ff-fitcard .prose hr { border-top-color: rgba(0,0,0,0.07) !important; }
body.ff-light #ff-listing .prose em { color: #CCCCCC !important; }
body.ff-light #ff-listing .prose code {
    background: rgba(201,101,34,0.07) !important;
    border-color: rgba(201,101,34,0.14) !important;
    color: #A85218 !important;
}
body.ff-light #ff-fitcard .prose { border-left-color: rgba(201,101,34,0.18) !important; }
body.ff-light #ff-fitcard .prose p { color: #7A7A76 !important; }

/* outfit */
body.ff-light .outfit-intro { color: #888888 !important; }
body.ff-light .outfit-accordion { border-color: rgba(0,0,0,0.08) !important; }
body.ff-light .outfit-accordion[open] {
    border-color: rgba(201,101,34,0.20) !important;
    box-shadow: 0 4px 14px rgba(0,0,0,0.06) !important;
}
body.ff-light .outfit-summary { background: #F0ECE4 !important; }
body.ff-light .outfit-summary:hover { background: #E8E2D8 !important; }
body.ff-light .outfit-label { color: #C96522 !important; }
body.ff-light .outfit-preview { color: #999999 !important; }
body.ff-light details[open] .outfit-preview { color: #666660 !important; }
body.ff-light .outfit-chevron { color: #CCCCCC !important; }
body.ff-light details[open] .outfit-chevron { color: #C96522 !important; }
body.ff-light .outfit-content { background: #FAFAF7 !important; border-top-color: rgba(0,0,0,0.05) !important; }
body.ff-light .outfit-step-text,
body.ff-light .outfit-step-solo { color: #5A5A56 !important; }
body.ff-light .outfit-step::before {
    background: rgba(201,101,34,0.08) !important;
    border-color: rgba(201,101,34,0.16) !important;
    color: #C96522 !important;
}
body.ff-light .outfit-closing { color: #BBBBBB !important; }

/* examples table */
body.ff-light .gradio-container table {
    background: #FAFAFA !important;
    border-color: rgba(0,0,0,0.07) !important;
}
body.ff-light .gradio-container th {
    background: #F0EDE6 !important;
    color: #AAAAAA !important;
    border-bottom-color: rgba(0,0,0,0.06) !important;
}
body.ff-light .gradio-container td {
    background: #FAFAFA !important;
    color: #888888 !important;
    border-bottom-color: rgba(0,0,0,0.04) !important;
}
body.ff-light .gradio-container tr:hover td {
    background: #FFF7EF !important;
    color: #1C1C1A !important;
}
body.ff-light .gradio-container .label-wrap,
body.ff-light .gradio-container .label-wrap span { color: #BBBBBB !important; }

/* ── style goal input ── */
#ff-style-goal { margin-top: 10px !important; }
#ff-style-goal label > span {
    font-family: 'Inter', sans-serif !important;
    font-size: 0.63rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    color: #2A2A2A !important;
}
#ff-style-goal input {
    font-family: 'Inter', sans-serif !important;
    font-style: italic !important;
    background: #141414 !important;
    color: #F0EDE8 !important;
    border-color: rgba(255,255,255,0.05) !important;
    border-radius: 10px !important;
    font-size: 0.875rem !important;
    transition: background 0.3s, color 0.3s, border-color 0.2s !important;
}
#ff-style-goal input::placeholder { color: #2E2E2E !important; font-style: italic !important; }

/* ── warning banner ── */
#ff-warning { min-height: 0 !important; }
.ff-warning-msg {
    background: rgba(244,162,97,0.06);
    border: 1px solid rgba(244,162,97,0.18);
    border-radius: 12px;
    padding: 11px 18px;
    color: #C4824A;
    font-family: 'Inter', sans-serif;
    font-size: 0.82rem;
    line-height: 1.6;
    margin: 0;
}

/* ── listing card (v2 HTML card — replaces prose markdown) ── */
.listing-card {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 10px 20px 20px;
}
.listing-img {
    width: 100%;
    border-radius: 12px;
    object-fit: cover;
    max-height: 180px;
    background: #1A1A1A;
    display: block;
}
.listing-body { display: flex; flex-direction: column; gap: 5px; }
.listing-title {
    font-family: 'Playfair Display', serif;
    font-size: 1.05rem;
    font-weight: 700;
    font-style: italic;
    color: #EDEAE4;
    line-height: 1.3;
    margin: 0;
    transition: color 0.3s;
}
.listing-meta {
    font-family: 'Inter', sans-serif;
    font-size: 0.78rem;
    color: #555550;
    margin: 0;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 5px;
    transition: color 0.3s;
}
.listing-price { color: #F4A261 !important; font-weight: 700; }
.listing-sep { color: #282828; }
.listing-colors {
    font-family: 'Inter', sans-serif;
    font-size: 0.75rem;
    color: #333333;
    margin: 0;
    font-style: italic;
    transition: color 0.3s;
}
.listing-hr { border: none; border-top: 1px solid rgba(255,255,255,0.05); margin: 6px 0; }
.listing-desc {
    font-family: 'Inter', sans-serif;
    font-size: 0.85rem;
    color: #9A9A94;
    line-height: 1.7;
    margin: 0;
    transition: color 0.3s;
}
.listing-tags { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 2px; }
.listing-tag {
    background: rgba(244,162,97,0.08);
    border: 1px solid rgba(244,162,97,0.14);
    color: #C4824A;
    border-radius: 5px;
    padding: 2px 7px;
    font-family: 'Inter', sans-serif;
    font-size: 0.7rem;
    font-weight: 500;
    letter-spacing: 0.03em;
}
.listing-buy {
    display: inline-block;
    margin-top: 12px;
    padding: 8px 20px;
    background: #F4A261;
    color: #0A0A0A;
    border-radius: 8px;
    font-family: 'Inter', sans-serif;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-decoration: none;
    text-transform: uppercase;
    transition: background 0.2s;
    cursor: pointer;
}
.listing-buy:hover { background: #E8935A; }
.listing-error {
    padding: 16px 20px;
    color: #555550;
    font-family: 'Inter', sans-serif;
    font-size: 0.875rem;
    line-height: 1.7;
}

/* light mode — new elements */
body.ff-light .ff-warning-msg {
    background: rgba(201,101,34,0.05) !important;
    border-color: rgba(201,101,34,0.18) !important;
    color: #A85218 !important;
}
body.ff-light #ff-style-goal label > span { color: #AAAAAA !important; }
body.ff-light #ff-style-goal input {
    background: #FFFFFF !important;
    color: #1C1C1A !important;
    border-color: rgba(0,0,0,0.06) !important;
}
body.ff-light #ff-style-goal input::placeholder { color: #CCCCCC !important; }
body.ff-light .listing-title { color: #1C1C1A !important; }
body.ff-light .listing-meta { color: #888888 !important; }
body.ff-light .listing-price { color: #C96522 !important; }
body.ff-light .listing-sep { color: #DDDDDD !important; }
body.ff-light .listing-colors { color: #AAAAAA !important; }
body.ff-light .listing-hr { border-top-color: rgba(0,0,0,0.06) !important; }
body.ff-light .listing-desc { color: #5A5A56 !important; }
body.ff-light .listing-img { background: #E8E4DC !important; }
body.ff-light .listing-tag {
    background: rgba(201,101,34,0.07) !important;
    border-color: rgba(201,101,34,0.14) !important;
    color: #A85218 !important;
}
body.ff-light .listing-buy { background: #C96522 !important; color: #FFFFFF !important; }
body.ff-light .listing-buy:hover { background: #A85218 !important; }
body.ff-light .listing-error { color: #888888 !important; }
"""

# ── JS ────────────────────────────────────────────────────────────────────────

# On load: ensure dark default (remove any stale ff-light class)
_JS_INIT = "() => { document.body.classList.remove('ff-light'); }"

# Pure client-side toggle — no Python fn needed, CSS ::after handles the label
_JS_TOGGLE = "() => { document.body.classList.toggle('ff-light'); }"


# ── Wardrobe descriptions ─────────────────────────────────────────────────────

_WARDROBE_DESC = {
    "Demo wardrobe": (
        "Uses a pre-loaded closet with real pieces — "
        "outfit combos will name specific items you already own."
    ),
    "No wardrobe": (
        "No closet needed — AI gives general styling advice "
        "based on the item's look, fit, and vibe."
    ),
}


def _wardrobe_info_html(choice: str) -> str:
    text = _WARDROBE_DESC.get(choice, "")
    return f'<p class="wardrobe-info">{text}</p>'


# ── Outfit formatter ──────────────────────────────────────────────────────────

def _sentences(text: str) -> list[str]:
    """Split a paragraph into individual styling sentences."""
    parts = re.split(r'(?<=[.!])\s+(?=[A-Z"\'(—])', text.strip())
    return [s.strip() for s in parts if s.strip()]


def _steps_html(para: str) -> str:
    """Render an outfit paragraph as a numbered steps list."""
    sentences = _sentences(para)
    if len(sentences) <= 1:
        return f'<p class="outfit-step-solo">{para}</p>'
    items = "".join(
        f'<li class="outfit-step"><span class="outfit-step-text">{s}</span></li>'
        for s in sentences
    )
    return f'<ol class="outfit-steps">{items}</ol>'


def _format_outfit_html(outfit_text: str) -> str:
    """
    Parse the LLM's outfit suggestion into HTML:
    - intro line as plain text
    - each outfit combo as a collapsible accordion
    - combo body split into numbered styling steps
    """
    if not outfit_text or not outfit_text.strip():
        return '<div class="outfit-container"><p class="outfit-step-solo">No outfit suggestion available.</p></div>'

    paragraphs = [p.strip() for p in outfit_text.split('\n\n') if p.strip()]

    if len(paragraphs) <= 1:
        return (
            '<div class="outfit-container">'
            f'<div class="outfit-content" style="border-radius:12px;border:1px solid rgba(255,255,255,0.07)">'
            f'{_steps_html(paragraphs[0] if paragraphs else outfit_text)}'
            '</div></div>'
        )

    intro = paragraphs[0]

    _closers = ('both', 'either', 'these', 'you can always', 'have fun',
                'enjoy', 'remember', 'hope', 'feel free', 'whichever',
                'mix and match', 'experiment')
    has_closing = paragraphs[-1].lower().startswith(_closers)
    outfit_paras = paragraphs[1:-1] if (has_closing and len(paragraphs) > 2) else paragraphs[1:]
    closing = paragraphs[-1] if has_closing else None

    options_html = ""
    for i, para in enumerate(outfit_paras, 1):
        first = _sentences(para)
        preview = first[0] if first else (para[:65].rstrip() + "…")

        options_html += (
            f'<details class="outfit-accordion">'
            f'<summary class="outfit-summary">'
            f'<span class="outfit-label">Option {i}</span>'
            f'<span class="outfit-preview">{preview}</span>'
            f'<span class="outfit-chevron">&#9660;</span>'
            f'</summary>'
            f'<div class="outfit-content">{_steps_html(para)}</div>'
            f'</details>'
        )

    html = (
        f'<div class="outfit-container">'
        f'<p class="outfit-intro">{intro}</p>'
        f'<div class="outfit-options">{options_html}</div>'
    )
    if closing:
        html += f'<p class="outfit-closing">{closing}</p>'
    return html + '</div>'


# ── Listing HTML renderer ─────────────────────────────────────────────────────

def _format_listing_html(item: dict) -> str:
    """Render a normalized listing dict as a styled HTML card with image and buy link."""
    title     = _html.escape(item.get("title", ""))
    price     = item.get("price", 0)
    platform  = item.get("platform", "eBay")
    size      = item.get("size", "")
    condition = item.get("condition", "")
    colors    = ", ".join(item.get("colors", []))
    desc      = _html.escape(item.get("description", ""))
    tags      = item.get("style_tags", [])
    image_url = item.get("image_url", "")
    item_url  = item.get("item_url", "")

    # Don't show description if empty or identical to title
    show_desc = desc and desc.strip().lower() != title.strip().lower()

    img_html = (
        f'<img src="{_html.escape(image_url)}" alt="{title}" class="listing-img" '
        f'onerror="this.style.display=\'none\'" />'
        if image_url else ""
    )
    size_html = (
        f'<span class="listing-sep">·</span><span>Size {_html.escape(size)}</span>'
        if size and size != "Not listed" else ""
    )
    colors_html = f'<p class="listing-colors">{_html.escape(colors)}</p>' if colors else ""
    desc_html   = f'<p class="listing-desc">{desc}</p>' if show_desc else ""
    tags_html   = "".join(
        f'<span class="listing-tag">{_html.escape(t)}</span>' for t in tags
    )
    buy_html = (
        f'<a href="{_html.escape(item_url)}" target="_blank" rel="noopener noreferrer" '
        f'class="listing-buy">Shop on eBay &rarr;</a>'
        if item_url else ""
    )

    return f"""
<div class="listing-card">
  {img_html}
  <div class="listing-body">
    <h3 class="listing-title">{title}</h3>
    <p class="listing-meta">
      <strong class="listing-price">${price:.2f}</strong>
      <span class="listing-sep">·</span><span>{_html.escape(platform)}</span>
      {size_html}
      <span class="listing-sep">·</span><span>{_html.escape(condition)}</span>
    </p>
    {colors_html}
    <hr class="listing-hr" />
    {desc_html}
    <div class="listing-tags">{tags_html}</div>
    {buy_html}
  </div>
</div>
"""


# ── Query handler ─────────────────────────────────────────────────────────────

def handle_query(
    user_query: str,
    wardrobe_choice: str,
    style_goal: str,
) -> tuple[str, str, str, str]:
    """Returns (listing_html, outfit_html, fitcard_text, warning_html)."""
    if not user_query or not user_query.strip():
        return "", "", "", ""

    wardrobe   = get_example_wardrobe() if wardrobe_choice == "Demo wardrobe" else get_empty_wardrobe()
    clean_goal = style_goal.strip() if style_goal and style_goal.strip() else None

    session = run_agent(
        query=user_query.strip(),
        wardrobe=wardrobe,
        style_goal=clean_goal,
    )

    warning_html = (
        f'<div class="ff-warning-msg">{_html.escape(session["warning"])}</div>'
        if session.get("warning") else ""
    )

    if session["error"]:
        error_html = f'<div class="listing-error">{_html.escape(session["error"])}</div>'
        return error_html, "", "", warning_html

    return (
        _format_listing_html(session["selected_item"]),
        _format_outfit_html(session["outfit_suggestion"]),
        session["fit_card"] or "",
        warning_html,
    )


# ── Interface ─────────────────────────────────────────────────────────────────

# [query, wardrobe_choice, style_goal]
EXAMPLE_QUERIES = [
    ["vintage graphic tee under $30",        "Demo wardrobe", "90s streetwear"],
    ["oversized blazer size M under $60",    "Demo wardrobe", "dark academia"],
    ["flowy midi skirt under $40",           "Demo wardrobe", "cottagecore"],
    ["black combat boots size 8",            "No wardrobe",   "grunge"],
    ["cozy knit cardigan under $50",         "Demo wardrobe", "dark academia"],
]


def build_interface():
    with gr.Blocks(title="FitFindr") as demo:

        # Pure JS toggle — label driven by CSS ::after, no Python state needed
        theme_btn = gr.Button(" ", elem_id="ff-theme-btn", size="sm")

        gr.HTML("""
        <div class="ff-hero">
          <span class="ff-logo">Fit<span class="ff-accent">Findr</span></span>
          <span class="ff-tagline">secondhand &middot; styled &middot; yours</span>
        </div>
        """)

        with gr.Group(elem_id="ff-search"):
            with gr.Row():
                query_input = gr.Textbox(
                    label="What are you looking for?",
                    placeholder="e.g. vintage graphic tee under $30, size M",
                    lines=2,
                    scale=3,
                    elem_id="ff-query",
                )
                with gr.Column(scale=1):
                    wardrobe_choice = gr.Radio(
                        choices=["Demo wardrobe", "No wardrobe"],
                        value="Demo wardrobe",
                        label="Wardrobe",
                        elem_id="ff-wardrobe",
                    )
                    wardrobe_info = gr.HTML(
                        _wardrobe_info_html("Demo wardrobe"),
                        elem_id="ff-wardrobe-info",
                    )
            # Optional style goal — spans the full search card width
            style_goal_input = gr.Textbox(
                label="What look are you going for? (optional)",
                placeholder="e.g. dark academia, 90s streetwear, soft girl, minimalist clean...",
                lines=1,
                elem_id="ff-style-goal",
            )

        # Non-fatal warning (e.g. borderline query) shown between search and results
        warning_output = gr.HTML(elem_id="ff-warning")

        submit_btn = gr.Button("Find it", variant="primary", size="lg", elem_id="ff-submit")

        with gr.Row(equal_height=True):
            with gr.Column(elem_classes=["output-card"]):
                gr.HTML('<span class="card-label">Top listing found</span>')
                listing_output = gr.HTML(elem_id="ff-listing")

            with gr.Column(elem_classes=["output-card"]):
                gr.HTML('<span class="card-label">Outfit ideas</span>')
                outfit_output = gr.HTML(elem_id="ff-outfit")

            with gr.Column(elem_classes=["output-card"]):
                gr.HTML('<span class="card-label">Your fit card</span>')
                fitcard_output = gr.Markdown(elem_id="ff-fitcard", show_label=False)

        gr.Examples(
            examples=EXAMPLE_QUERIES,
            inputs=[query_input, wardrobe_choice, style_goal_input],
            label="Try these searches",
        )

        # ── event wiring ──────────────────────────────────────────────────────

        _inputs  = [query_input, wardrobe_choice, style_goal_input]
        _outputs = [listing_output, outfit_output, fitcard_output, warning_output]

        submit_btn.click(fn=handle_query, inputs=_inputs, outputs=_outputs)
        query_input.submit(fn=handle_query, inputs=_inputs, outputs=_outputs)

        wardrobe_choice.change(
            fn=_wardrobe_info_html,
            inputs=[wardrobe_choice],
            outputs=[wardrobe_info],
        )

        theme_btn.click(fn=None, js=_JS_TOGGLE)
        demo.load(fn=None, js=_JS_INIT)

    return demo


if __name__ == "__main__":
    demo = build_interface()
    demo.launch(css=CSS, theme=_theme)
