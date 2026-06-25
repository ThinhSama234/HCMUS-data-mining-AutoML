"""Shared visual identity for the console — ported from the approved mockup.

Teal-ink + amber-signal "engineering console" look. Streamlit's own widgets are lightly
themed; the high-fidelity cards/pills/tables are rendered as controlled HTML so they match
the mockup regardless of Streamlit's internal class names.
"""
from __future__ import annotations

import os
import sys

# Make repo root importable (analysis/, console/) whether a page is run via
# the nav entrypoint or directly (tests).
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

TEAL = "#0C6E6A"
AMBER = "#C9620A"

_CSS = """
<style>
:root{ --teal:#0C6E6A; --amber:#C9620A; --ink:#14201F; --muted:#5C6B69;
       --line:#DCE3E1; --ground:#F4F6F5; --ok:#2E7D5B; --run:#2D6CB0; --fail:#B23A48; --warn:#B5860B; }
.stApp{ background:var(--ground); }
section.main .block-container{ padding-top:1.6rem; max-width:1200px; }
/* kill Streamlit's auto heading-anchor (the ⚓ link icon) — it reads as visual noise */
[data-testid="stHeaderActionElements"]{ display:none !important; }
h1,h2,h3{ letter-spacing:-.02em; color:var(--ink); }
[data-testid="stHeading"] h3,[data-testid="stHeading"] h2{ font-size:17px; font-weight:700;
       letter-spacing:-.01em; margin-bottom:.1rem; }
/* sidebar = deep petrol */
[data-testid="stSidebar"]{ background:#0E2A28; }
[data-testid="stSidebar"] *{ color:#cfe0dd; }
[data-testid="stSidebar"] a[aria-current="page"]{ background:var(--teal)!important; color:#fff!important; border-radius:8px; }
/* make the sidebar a full-height column so the footer can sink to the bottom */
[data-testid="stSidebar"] > div:first-child{ display:flex; flex-direction:column; height:100%; }
[data-testid="stSidebarUserContent"]{ margin-top:auto; }
.navfoot{ padding:13px 6px 4px; margin-top:14px; border-top:1px solid #ffffff1a; }
.navfoot .nf-title{ font-weight:700; font-size:12.5px; color:#dcebe8; letter-spacing:-.01em; }
.navfoot .nf-sub{ font-size:11px; color:#86a09d; margin-top:2px; line-height:1.4; }
.navfoot .nf-meta{ font-family:ui-monospace,Menlo,monospace; font-size:9.5px; letter-spacing:.07em;
                   text-transform:uppercase; color:#6c8783; margin-top:7px; }
/* buttons — one shared shape, then two intents (amber primary / ghost secondary) */
.stButton>button{ border-radius:9px; font-weight:600; font-size:13.5px; letter-spacing:-.005em;
       padding:.5rem 1.15rem; min-height:40px; transition:background .12s,border-color .12s,box-shadow .12s,color .12s,transform .05s; }
.stButton>button:active{ transform:translateY(1px); }
.stButton>button:focus:not(:active){ box-shadow:none; }
/* secondary / default → quiet ghost: hairline border, ink text, teal on hover */
.stButton>button[kind="secondary"]{ background:#fff; border:1px solid var(--line); color:var(--ink); }
.stButton>button[kind="secondary"]:hover{ border-color:var(--teal); color:var(--teal); background:#fff; }
.stButton>button[kind="secondary"]:focus-visible{ outline:2px solid #0c6e6a44; outline-offset:2px; }
/* primary → amber signal with depth + darken-on-hover (not the flat bright fill) */
.stButton>button[kind="primary"]{ background:var(--amber); border:1px solid var(--amber); color:#fff;
       box-shadow:0 1px 2px #c9620a33; }
.stButton>button[kind="primary"]:hover{ background:#ad550a; border-color:#ad550a; color:#fff;
       box-shadow:0 3px 10px #c9620a4d; }
.stButton>button[kind="primary"]:focus-visible{ outline:2px solid #c9620a66; outline-offset:2px; }
/* multiselect chips → soft teal tag (not Streamlit's default red) */
[data-baseweb="tag"]{ background:#0c6e6a !important; border-radius:7px !important; }
[data-baseweb="tag"] span{ color:#fff !important; }
[data-baseweb="tag"] svg{ fill:#ffffffcc !important; }
[data-baseweb="tag"] [role="button"]:hover{ background:#ffffff33 !important; }
/* custom blocks */
.headwrap{ padding-bottom:15px; margin-bottom:22px; border-bottom:1px solid var(--line); }
.kicker{ display:block; font-family:ui-monospace,Menlo,monospace; font-size:10.5px; font-weight:600;
         letter-spacing:.11em; text-transform:uppercase; color:var(--teal); margin:0 0 7px; }
.pagehead{ display:flex; align-items:center; gap:12px; margin:0; }
.pagehead h1{ margin:0; font-size:28px; font-weight:700; line-height:1.05; letter-spacing:-.025em; color:var(--ink); }
.livebadge{ display:inline-flex; align-items:center; gap:6px; font-size:11px; font-weight:600;
            padding:3px 11px; border-radius:20px; line-height:1; }
.livebadge.live{ background:#0c6e6a14; color:var(--teal); }
.livebadge.mock{ background:#5c6b6914; color:var(--muted); }
.livebadge .dot{ width:7px; height:7px; border-radius:50%; background:currentColor; }
.livebadge.live .dot{ animation:pulse 2.2s ease-out infinite; }
@keyframes pulse{ 0%{box-shadow:0 0 0 0 #0c6e6a55} 70%{box-shadow:0 0 0 6px #0c6e6a00} 100%{box-shadow:0 0 0 0 #0c6e6a00} }
.subhead{ color:var(--muted); font-size:13px; line-height:1.5; margin:.5rem 0 0; max-width:66ch; }
.cards{ display:grid; gap:14px; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); margin:14px 0; }
.card{ background:#fff; border:1px solid var(--line); border-radius:11px; padding:16px;
       height:100%; box-sizing:border-box; }
.card.dash{ border-style:dashed; border-color:var(--teal); }
.cards a > .card{ cursor:pointer; transition:border-color .12s, box-shadow .12s; }
.cards a:hover > .card{ border-color:var(--teal); box-shadow:0 1px 8px #0c6e6a22; }
.skel{ background:linear-gradient(90deg,#eef2f0,#e3e9e7,#eef2f0); background-size:200% 100%;
       border-radius:6px; height:14px; margin:8px 0; animation:skel 1.1s ease-in-out infinite; }
@keyframes skel{ 0%{background-position:200% 0} 100%{background-position:-200% 0} }
.card .lbl,.section-lbl{ font-family:ui-monospace,Menlo,monospace; font-size:10.5px; letter-spacing:.06em;
            text-transform:uppercase; color:var(--muted); }
.section-lbl{ display:block; margin:.2rem 0 .5rem; }
.card h3{ margin:.2rem 0; font-size:15px; }
.card .num{ font-size:30px; font-weight:700; letter-spacing:-.02em; }
.card .num.teal{ color:var(--teal); } .card .num.amber{ color:var(--amber); }
.card .note,.note{ color:var(--muted); font-size:12.5px; }
/* tables scroll inside their own box on narrow screens — never blow out the page width */
.table-wrap{ overflow-x:auto; -webkit-overflow-scrolling:touch; }
.amlb-table{ border-collapse:collapse; width:100%; font-size:13.5px; background:#fff;
             border:1px solid var(--line); border-radius:11px; overflow:hidden; }
.amlb-table th{ text-align:left; padding:10px 12px; font-family:ui-monospace,Menlo,monospace; font-size:10.5px;
                letter-spacing:.06em; text-transform:uppercase; color:var(--muted); border-bottom:1px solid var(--line); }
.amlb-table td{ padding:10px 12px; border-bottom:1px solid var(--line); }
.amlb-table tr:last-child td{ border-bottom:none; }
.mono{ font-family:ui-monospace,Menlo,monospace; }
.pill{ font-family:ui-monospace,Menlo,monospace; font-size:11px; padding:2px 9px; border-radius:20px; font-weight:600; }
.pill.ok{ background:#2e7d5b1a; color:var(--ok);} .pill.run{ background:#2d6cb01a; color:var(--run);}
.pill.fail{ background:#b23a481a; color:var(--fail);} .pill.queue{ background:#5c6b6914; color:var(--muted);}
.pill.warn{ background:#b5860b1a; color:var(--warn);}
.hint{ border-left:3px solid var(--amber); background:#c9620a14; padding:10px 14px; border-radius:0 8px 8px 0;
       font-size:13px; margin:14px 0; }
/* ---- mobile (≤640px): tighter gutters, 2-up cards, calmer type ---- */
@media (max-width:640px){
  section.main .block-container{ padding-top:1rem; padding-left:1rem; padding-right:1rem; }
  .headwrap{ margin-bottom:16px; padding-bottom:12px; }
  .pagehead{ flex-wrap:wrap; gap:8px; }
  .pagehead h1{ font-size:23px; }
  .subhead{ font-size:12.5px; }
  .cards{ grid-template-columns:repeat(2,1fr); gap:10px; margin:12px 0; }
  .card{ padding:13px; }
  .card .num{ font-size:23px; }
  .card h3{ font-size:14px; }
  .amlb-table{ font-size:12.5px; }
  .amlb-table th,.amlb-table td{ padding:8px 9px; }
  .stButton>button{ min-height:44px; }   /* comfortable tap target */
}
</style>
"""


def inject():
    """Inject the shared stylesheet (call once per page render)."""
    import streamlit as st
    st.markdown(_CSS, unsafe_allow_html=True)


def pagehead(title, subtitle=None, live=True, kicker=None):
    """Page header: optional mono kicker, title + live/preview badge, muted subtitle, hairline rule.

    The whole block is wrapped in ``.headwrap`` so every page gets the same separator and rhythm.
    ``kicker`` is an optional uppercase eyebrow (e.g. the section name) shown above the title.
    """
    import streamlit as st
    kind = "live" if live else "mock"
    label = "Live" if live else "Preview"
    badge = f'<span class="livebadge {kind}"><span class="dot"></span>{label}</span>'
    eyebrow = f'<span class="kicker">{kicker}</span>' if kicker else ""
    sub = f'<div class="subhead">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f'<div class="headwrap">{eyebrow}'
        f'<div class="pagehead"><h1>{title}</h1>{badge}</div>{sub}</div>',
        unsafe_allow_html=True,
    )


def pill(text, kind):
    return f'<span class="pill {kind}">{text}</span>'


def coming_soon(note):
    """A centered 'coming soon' placeholder for sections without a backend yet."""
    import streamlit as st
    st.markdown(
        '<div class="card" style="text-align:center;padding:48px 24px;border-style:dashed;'
        'border-color:var(--line)">'
        '<div style="font-size:34px;margin-bottom:6px">🚧</div>'
        '<div style="font-weight:700;font-size:16px;margin-bottom:6px">Coming soon</div>'
        f'<div class="note" style="max-width:440px;margin:0 auto">{note}</div></div>',
        unsafe_allow_html=True,
    )


def table(headers, rows):
    """Render a list-of-rows as the styled HTML table (rows are HTML-ready strings)."""
    import streamlit as st
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    st.markdown(
        f'<div class="table-wrap"><table class="amlb-table">'
        f'<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>',
        unsafe_allow_html=True,
    )


def sidebar_footer(title="AutoML Bench", sub="AMLB-style framework benchmark", meta="v0.1 · thesis build"):
    """Pin a small identity footer to the bottom of the sidebar nav.

    Call once, before ``nav.run()`` — pages may ``st.stop()`` mid-render, so anything placed
    after ``nav.run()`` can be skipped. The bottom-pinning is handled by CSS (margin-top:auto).
    """
    import streamlit as st
    st.sidebar.markdown(
        f'<div class="navfoot"><div class="nf-title">{title}</div>'
        f'<div class="nf-sub">{sub}</div><div class="nf-meta">{meta}</div></div>',
        unsafe_allow_html=True,
    )


def metric_cards(items):
    """Render a responsive KPI row using the shared .card style.

    ``items`` is a list of dicts: {label, value, note?, tone?} where tone ∈ {"teal","amber",""}.
    """
    import streamlit as st
    cells = []
    for it in items:
        tone = it.get("tone", "")
        note = f'<div class="note">{it["note"]}</div>' if it.get("note") else ""
        cells.append(
            f'<div class="card"><div class="lbl">{it["label"]}</div>'
            f'<div class="num {tone}">{it["value"]}</div>{note}</div>'
        )
    st.markdown(f'<div class="cards">{"".join(cells)}</div>', unsafe_allow_html=True)


# Brand colorway for charts — teal lead, amber signal, then calm neutrals/status hues.
CHART_COLORWAY = [TEAL, AMBER, "#5C6B69", "#2D6CB0", "#B5860B", "#B23A48"]


def style_fig(fig, *, height=None):
    """Stamp the console's visual identity onto a Plotly figure.

    Replaces Plotly's default blue/purple palette with the brand colorway, flattens the
    chrome (transparent canvas, hairline grid in --line), and tightens margins so charts
    read as part of the page rather than a bolted-on widget. Returns the same figure.
    """
    has_title = bool(getattr(fig.layout.title, "text", None))
    fig.update_layout(
        colorway=CHART_COLORWAY,
        font=dict(family="ui-sans-serif, -apple-system, Segoe UI, Roboto, sans-serif",
                  size=13, color="#14201F"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        title=dict(font=dict(size=15, color="#14201F"), x=0, xanchor="left"),
        margin=dict(l=8, r=14, t=46 if has_title else 14, b=8),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=12),
                    orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hoverlabel=dict(font=dict(family="ui-monospace, Menlo, monospace", size=12),
                        bgcolor="#14201F"),
    )
    grid = dict(showgrid=True, gridcolor="#DCE3E1", gridwidth=1, zeroline=False,
                linecolor="#DCE3E1", ticks="outside", tickcolor="#DCE3E1")
    fig.update_xaxes(**grid)
    fig.update_yaxes(**grid)
    if height:
        fig.update_layout(height=height)
    return fig
