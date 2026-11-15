import html
import importlib
import json
import re
import warnings
from contextlib import contextmanager

import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from llm.ollama_client import extract_requirements
from llm.database_profiler import profile_database
from validation.requirement_validator import (
    validate_requirements,
    CRITERION_MAPPING,
)
from database.applications import save_application
from database.connection import get_connection
from database.migrations import ensure_catalog
from decision_engine.analysis import analyze, contributions
from decision_engine.weighted_sum import recommend

# pandas warns when it is given a raw psycopg2 connection; it still works.
warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy")


# =========================================================
# SCHEMA DESIGNER IMPORT
# =========================================================
# The designer module can live under any of these names. Add yours here
# if it is called something else (it must expose generate_database_design).

DESIGNER_MODULES = (
    "database_designer",
    "llm.database_designer",
    "llm.groq_client",
    "llm.groq_designer",
    "llm.schema_designer",
    "llm.groq_schema",
)


def load_designer():
    """Return (function, error_message). Never raises."""
    last_error = "No designer module found."
    for module_name in DESIGNER_MODULES:
        try:
            module = importlib.import_module(module_name)
            return module.generate_database_design, None
        except ModuleNotFoundError as exc:
            # Missing module is expected; a missing dependency (e.g. groq) is not.
            if exc.name and exc.name != module_name and not module_name.startswith(exc.name):
                last_error = f"{module_name} needs a missing package: {exc.name}"
        except Exception as exc:  # noqa: BLE001
            last_error = f"{module_name} failed to load: {exc}"
    return None, last_error


generate_database_design, DESIGNER_ERROR = load_designer()


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="DB Selector",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource(show_spinner="Preparing the catalog...")
def prepare_catalog():
    """Add new score columns and load the curated catalog once per server run."""
    ensure_catalog()
    return True


try:
    prepare_catalog()
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not prepare the catalog: {exc}")
    st.stop()


# =========================================================
# GLOBAL STYLING  (blueprint: ink-blue paper, amber highlighter)
# =========================================================

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@500;600;700&family=Instrument+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

    :root {
        --bg: #0a0f16;
        --panel: rgba(148,180,255,0.045);
        --panel-strong: rgba(148,180,255,0.08);
        --border: rgba(148,180,255,0.15);
        --text: #e6ebf3;
        --muted: #8d9bb0;
        --amber: #f5b942;
        --amber-hover: #ffd070;
        --blue: #7aa2ff;
    }

    .stApp {
        background-color: var(--bg);
        background-image:
            linear-gradient(rgba(148,180,255,0.035) 1px, transparent 1px),
            linear-gradient(90deg, rgba(148,180,255,0.035) 1px, transparent 1px);
        background-size: 36px 36px;
        font-family: 'Instrument Sans', sans-serif;
        color: var(--text);
    }

    header[data-testid="stHeader"] { background: transparent; }

    .block-container {
        max-width: 1280px;
        padding: 2.4rem 3rem 4rem;
    }

    h1, h2, h3, h4 {
        font-family: 'Bricolage Grotesque', sans-serif !important;
        letter-spacing: -0.03em;
        color: var(--text);
    }
    h1 {
        font-size: clamp(2.2rem, 4vw, 3.4rem) !important;
        font-weight: 600 !important;
        line-height: 1.05 !important;
        margin-bottom: 0.4rem !important;
    }
    h2, h3 { font-weight: 600 !important; }
    p, label, li { line-height: 1.65; }

    code, pre, [data-testid="stCode"] * {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.85rem !important;
    }

    .lede {
        color: var(--muted);
        font-size: 1.08rem;
        max-width: 680px;
        margin: 0 0 1.6rem;
    }

    /* ---------- cards & metrics ---------- */
    [data-testid="stMetric"] {
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 1.1rem 1.2rem;
    }
    [data-testid="stMetricLabel"] { color: var(--muted); }
    [data-testid="stMetricValue"] {
        font-family: 'Bricolage Grotesque', sans-serif;
        font-weight: 600;
    }

    [data-testid="stVerticalBlockBorderWrapper"] {
        border-color: var(--border);
        border-radius: 14px;
        background: var(--panel);
    }

    [data-testid="stDataFrame"] {
        border: 1px solid var(--border);
        border-radius: 10px;
        overflow: hidden;
    }

    /* ---------- buttons ---------- */
    div.stButton > button,
    div.stDownloadButton > button,
    div[data-testid="stFormSubmitButton"] > button {
        min-height: 44px;
        border: 1px solid var(--border);
        border-radius: 8px;
        font-weight: 600;
        background: var(--panel-strong);
        color: var(--text);
        transition: border-color 160ms ease, background 160ms ease;
    }
    div.stButton > button:hover,
    div.stDownloadButton > button:hover,
    div[data-testid="stFormSubmitButton"] > button:hover {
        border-color: var(--amber);
        color: var(--text);
    }
    div.stButton > button[kind="primary"],
    div[data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"] {
        background: var(--amber);
        border-color: var(--amber);
        color: #1b1405;
    }
    div.stButton > button[kind="primary"]:hover,
    div[data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"]:hover {
        background: var(--amber-hover);
        border-color: var(--amber-hover);
        color: #1b1405;
    }
    button:focus-visible { outline: 2px solid var(--blue) !important; outline-offset: 2px; }

    /* ---------- inputs ---------- */
    div[data-baseweb="input"] > div,
    div[data-baseweb="textarea"] > div,
    div[data-baseweb="select"] > div {
        border-radius: 8px;
        background: rgba(10,15,22,0.7);
        border-color: var(--border);
    }

    /* ---------- tabs & expanders ---------- */
    button[data-baseweb="tab"] {
        font-family: 'Bricolage Grotesque', sans-serif;
        font-weight: 500;
    }
    [data-testid="stExpander"] {
        border: 1px solid var(--border);
        border-radius: 10px;
        background: var(--panel);
    }

    /* ---------- sidebar ---------- */
    [data-testid="stSidebar"] {
        background: #080c12;
        border-right: 1px solid var(--border);
    }
    .brand {
        font-family: 'Bricolage Grotesque', sans-serif;
        font-size: 1.5rem;
        font-weight: 700;
        letter-spacing: -0.03em;
    }
    .brand span { color: var(--amber); }
    .brand-sub { color: var(--muted); font-size: 0.85rem; }

    /* ---------- ranking bars ---------- */
    .rank-list { display: flex; flex-direction: column; gap: 0.55rem; margin: 0.4rem 0 1.2rem; }
    .rank-row {
        display: grid;
        grid-template-columns: 2rem minmax(7rem, 14rem) 1fr 4rem;
        align-items: center;
        gap: 0.9rem;
        padding: 0.7rem 1rem;
        border: 1px solid var(--border);
        border-radius: 10px;
        background: var(--panel);
    }
    .rank-row.lead {
        border-color: rgba(245,185,66,0.55);
        background: rgba(245,185,66,0.07);
    }
    .rank-no { color: var(--muted); font-family: 'JetBrains Mono', monospace; }
    .rank-row.lead .rank-no { color: var(--amber); }
    .rank-name { font-weight: 600; }
    .rank-track { height: 8px; border-radius: 99px; background: rgba(148,180,255,0.12); overflow: hidden; }
    .rank-fill { height: 100%; border-radius: 99px; background: var(--blue); }
    .rank-row.lead .rank-fill { background: var(--amber); }
    .rank-score {
        text-align: right;
        font-family: 'JetBrains Mono', monospace;
        font-weight: 500;
    }

    .tag {
        display: inline-block;
        border: 1px solid var(--border);
        color: var(--muted);
        border-radius: 6px;
        padding: 0.12rem 0.55rem;
        font-size: 0.8rem;
        margin-right: 0.35rem;
    }
    .tag.hot { border-color: rgba(245,185,66,0.5); color: var(--amber); }

    /* ---------- hero, pills, callouts ---------- */
    .hero {
        border: 1px solid var(--border);
        border-radius: 18px;
        padding: 1.8rem 2rem;
        margin-bottom: 1.4rem;
        background:
            radial-gradient(circle at 92% 0%, rgba(245,185,66,0.14), transparent 45%),
            radial-gradient(circle at 0% 100%, rgba(122,162,255,0.14), transparent 50%),
            var(--panel);
    }
    .pill {
        display: inline-block;
        border: 1px solid rgba(245,185,66,0.5);
        color: var(--amber);
        border-radius: 99px;
        padding: 0.15rem 0.7rem;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        margin-bottom: 0.7rem;
    }
    .callout {
        border: 1px solid var(--border);
        border-left: 3px solid var(--blue);
        border-radius: 8px;
        padding: 0.7rem 1rem;
        margin: 0.4rem 0 0.8rem;
        background: var(--panel);
    }
    .callout.warn { border-left-color: var(--amber); background: rgba(245,185,66,0.06); }
    .callout.good { border-left-color: #5fd39a; background: rgba(95,211,154,0.06); }

    /* ---------- sidebar navigation ---------- */
    [data-testid="stSidebar"] div[role="radiogroup"] { gap: 0.25rem; }
    [data-testid="stSidebar"] div[role="radiogroup"] > label {
        padding: 0.6rem 0.85rem;
        border-radius: 10px;
        border: 1px solid transparent;
        width: 100%;
        cursor: pointer;
        transition: background 160ms ease, border-color 160ms ease;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child { display: none; }
    [data-testid="stSidebar"] div[role="radiogroup"] > label:hover { background: var(--panel-strong); }
    [data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
        background: rgba(245,185,66,0.10);
        border-color: rgba(245,185,66,0.45);
        font-weight: 600;
    }

    /* ---------- score cards ---------- */
    .sc-list { display: flex; flex-direction: column; gap: 0.5rem; margin: 0.4rem 0 1rem; }
    .sc-row {
        display: grid;
        grid-template-columns: 9.5rem 3.2rem 1fr;
        gap: 1rem;
        align-items: start;
        padding: 0.8rem 1rem;
        border: 1px solid var(--border);
        border-radius: 12px;
        background: var(--panel);
    }
    .sc-name { font-weight: 600; }
    .sc-badge {
        display: inline-flex; align-items: center; justify-content: center;
        width: 2.6rem; height: 2.6rem; border-radius: 10px;
        font-family: 'JetBrains Mono', monospace; font-weight: 600; font-size: 1.05rem;
    }
    .sc-hi  { background: rgba(245,185,66,0.16); color: var(--amber); border: 1px solid rgba(245,185,66,0.5); }
    .sc-mid { background: rgba(122,162,255,0.14); color: var(--blue); border: 1px solid rgba(122,162,255,0.45); }
    .sc-lo  { background: rgba(255,119,119,0.10); color: #ff8f8f; border: 1px solid rgba(255,119,119,0.4); }
    .sc-why { line-height: 1.55; }
    .sc-ev { color: var(--muted); font-size: 0.88rem; margin-top: 0.3rem; line-height: 1.5; }
    .sc-src { font-size: 0.82rem; margin-top: 0.35rem; }
    .sc-src a { color: var(--blue); text-decoration: none; border-bottom: 1px dotted var(--blue); }
    .origin { font-size: 0.78rem; color: var(--muted); margin: 0.2rem 0 0.4rem; }

    /* ---------- database cards ---------- */
    .db-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 0.9rem; margin: 0.6rem 0 1.2rem; }
    .db-card {
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 1rem 1.1rem;
        background: var(--panel);
        transition: border-color 160ms ease, transform 160ms ease;
    }
    .db-card:hover { border-color: rgba(245,185,66,0.55); transform: translateY(-2px); }
    .db-card h4 { margin: 0.1rem 0 0.35rem; font-size: 1.15rem; }
    .db-card p { color: var(--muted); font-size: 0.9rem; margin: 0 0 0.7rem; line-height: 1.5; }
    .db-strengths { display: flex; flex-wrap: wrap; gap: 0.3rem; }

    .pick {
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 1rem 1.1rem;
        background: var(--panel);
        height: 100%;
    }
    .pick .k { color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.06em; }
    .pick .n { font-family: 'Bricolage Grotesque', sans-serif; font-size: 1.5rem; font-weight: 600; margin: 0.2rem 0; }
    .pick .s { color: var(--amber); font-family: 'JetBrains Mono', monospace; }
    .pick .r { color: var(--muted); font-size: 0.85rem; margin-top: 0.3rem; }

    @media (max-width: 768px) { .sc-row { grid-template-columns: 1fr; } }

    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
            animation-duration: 0.01ms !important;
            transition-duration: 0.01ms !important;
        }
    }
    @media (max-width: 768px) {
        .block-container { padding: 1.3rem 1rem 2rem; }
        .rank-row { grid-template-columns: 1.5rem 1fr 3.5rem; }
        .rank-track { display: none; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# SMALL UI HELPERS
# =========================================================

def stretch(fn, *args, **kwargs):
    """Full-width widget that works on old and new Streamlit versions."""
    try:
        return fn(*args, width="stretch", **kwargs)
    except (TypeError, st.errors.StreamlitAPIException):
        return fn(*args, use_container_width=True, **kwargs)


def page_header(title, subtitle):
    st.title(title)
    st.markdown(f'<p class="lede">{html.escape(subtitle)}</p>', unsafe_allow_html=True)


def ranking_bars(rankings):
    rows = []
    for position, item in enumerate(rankings, start=1):
        pct = max(0.0, min(100.0, item["score"] / 10 * 100))
        lead = " lead" if position == 1 else ""
        rows.append(
            f'<div class="rank-row{lead}">'
            f'<span class="rank-no">{position}</span>'
            f'<span class="rank-name">{html.escape(str(item["database_name"]))}</span>'
            f'<div class="rank-track"><div class="rank-fill" style="width:{pct:.1f}%"></div></div>'
            f'<span class="rank-score">{item["score"]:.2f}</span>'
            f"</div>"
        )
    st.markdown(f'<div class="rank-list">{"".join(rows)}</div>', unsafe_allow_html=True)


MERMAID_HTML = """
<!DOCTYPE html>
<html>
<head>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>
    <style>
        body { margin: 0; padding: 15px; background: transparent; font-family: Arial, sans-serif; }
        #diagram { width: 100%; overflow-x: auto; display: flex; justify-content: center; }
        #diagram svg { max-width: 100%; height: auto; }
        #error { color: #ff7777; white-space: pre-wrap; font-size: 14px; }
        #note { color: #8d9bb0; font-size: 13px; }
    </style>
</head>
<body>
    <div id="diagram"></div>
    <div id="note"></div>
    <div id="error"></div>
    <script>
        const source = DIAGRAM_SOURCE;
        let counter = 0;

        async function draw(text) {
            counter += 1;
            const result = await mermaid.render("class-diagram-" + counter, text);
            document.getElementById("diagram").innerHTML = result.svg;
        }

        async function run() {
            try {
                await draw(source);
            } catch (first) {
                // Retry once without relationship arrows.
                try {
                    const plain = source.split("\n")
                        .filter(function (l) { return l.indexOf("-->") === -1; })
                        .join("\n");
                    await draw(plain);
                    document.getElementById("note").textContent =
                        "Relationship arrows were left out because they could not be laid out.";
                } catch (error) {
                    document.getElementById("error").textContent =
                        "Diagram rendering failed: " + (error.message || error);
                }
            }
        }

        // Streamlit keeps inactive tabs hidden (display:none), where text and
        // boxes measure 0px and Mermaid's layout breaks. Wait until visible.
        function whenVisible() {
            if (window.innerWidth > 0 && document.body.clientWidth > 0) {
                run();
            } else {
                setTimeout(whenVisible, 250);
            }
        }

        if (typeof mermaid === "undefined") {
            document.getElementById("error").textContent =
                "Mermaid could not load (check your internet connection).";
        } else {
            // theme must be "base" for themeVariables to take effect.
            mermaid.initialize({
                startOnLoad: false,
                securityLevel: "strict",
                theme: "base",
                themeVariables: {
                    background: "#0a0f16",
                    primaryColor: "#151e2b",
                    primaryTextColor: "#e6ebf3",
                    primaryBorderColor: "#7aa2ff",
                    lineColor: "#f5b942",
                    secondaryColor: "#151e2b",
                    tertiaryColor: "#0a0f16",
                    fontFamily: "Arial"
                }
            });
            whenVisible();
        }
    </script>
</body>
</html>
"""


def render_mermaid(diagram):
    """Render a Mermaid class diagram inside Streamlit."""

    if not diagram or diagram.strip() in ("", "classDiagram"):
        st.info("No class diagram was generated.")
        return

    # json.dumps makes the source a safe JS string; "</" is escaped so the
    # source can never close the surrounding <script> tag.
    diagram_json = json.dumps(diagram).replace("</", "<\\/")

    page = MERMAID_HTML.replace("DIAGRAM_SOURCE", diagram_json)

    # Scale height with diagram size instead of a fixed 850px.
    height = max(320, min(1400, 140 + 24 * diagram.count("\n")))

    components.html(page, height=height, scrolling=True)



def callout(text, kind=""):
    st.markdown(f'<div class="callout {kind}">{html.escape(text)}</div>', unsafe_allow_html=True)


def heatmap(wide, fmt=".0f", domain=(1, 10)):
    """Altair heatmap from a wide frame (rows = databases, columns = criteria)."""
    long = (
        wide.reset_index()
        .melt(id_vars=wide.index.name or "index", var_name="Criterion", value_name="Value")
        .rename(columns={wide.index.name or "index": "Database"})
    )
    mid = (domain[0] + domain[1]) / 2
    base = alt.Chart(long).encode(
        x=alt.X("Criterion:N", sort=list(wide.columns), axis=alt.Axis(labelAngle=-30, title=None)),
        y=alt.Y("Database:N", sort=list(wide.index), axis=alt.Axis(title=None)),
    )
    rect = base.mark_rect(cornerRadius=3).encode(
        color=alt.Color(
            "Value:Q",
            scale=alt.Scale(domain=[domain[0], mid, domain[1]], range=["#16213a", "#4f74d9", "#f5b942"]),
            legend=None,
        ),
        tooltip=["Database", "Criterion", alt.Tooltip("Value:Q", format=".2f")],
    )
    text = base.mark_text(color="#e6ebf3", fontSize=12).encode(text=alt.Text("Value:Q", format=fmt))
    chart = (
        (rect + text)
        .properties(height=max(120, 30 * len(wide)))
        .configure(background="transparent")
        .configure_view(strokeWidth=0)
        .configure_axis(labelColor="#e6ebf3", labelFontSize=12)
    )
    stretch(st.altair_chart, chart)


def _txt(value):
    return "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value).strip()


ORIGIN_LABEL = {
    "curated": "Curated from official documentation",
    "web": "Researched on the web",
    "model": "Model estimate (no live web access)",
}


def score_cards(df):
    """Reasoning, evidence and source for each score, with full text (no truncation)."""
    rows = []
    for r in df.to_dict("records"):
        score = float(r["score"])
        tone = "sc-hi" if score >= 8 else "sc-mid" if score >= 5 else "sc-lo"
        why = _txt(r.get("reasoning")) or _txt(r.get("evidence"))
        evidence = _txt(r.get("evidence"))
        origin = _txt(r.get("origin"))
        extra = ""
        if origin != "curated" and evidence and evidence != why:
            extra = f'<div class="sc-ev">Evidence: {html.escape(evidence)}</div>'
        url = _txt(r.get("source_url"))
        if url.startswith(("http://", "https://")):
            safe = html.escape(url, quote=True)
            extra += f'<div class="sc-src"><a href="{safe}" target="_blank" rel="noopener noreferrer">Source</a></div>'
        rows.append(
            '<div class="sc-row">'
            f'<div class="sc-name">{html.escape(_txt(r["criterion"]))}</div>'
            f'<div><span class="sc-badge {tone}">{score:.0f}</span></div>'
            f'<div><div class="sc-why">{html.escape(why)}</div>{extra}</div>'
            "</div>"
        )
    origins = {ORIGIN_LABEL.get(_txt(o)) for o in df.get("origin", []) if _txt(o) in ORIGIN_LABEL}
    note = f'<div class="origin">{html.escape(" / ".join(sorted(origins)))}</div>' if origins else ""
    st.markdown(note + f'<div class="sc-list">{"".join(rows)}</div>', unsafe_allow_html=True)


def grouped_bars(pivot):
    long = pivot.reset_index().melt(id_vars="Database", var_name="Criterion", value_name="Score")
    chart = (
        alt.Chart(long)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X("Criterion:N", sort=list(pivot.columns), axis=alt.Axis(labelAngle=-30, title=None)),
            xOffset="Database:N",
            y=alt.Y("Score:Q", scale=alt.Scale(domain=[0, 10]), axis=alt.Axis(title=None)),
            color=alt.Color("Database:N", scale=alt.Scale(range=["#f5b942", "#7aa2ff", "#5fd39a", "#ff8f8f", "#c39bff", "#6fd6e8"])),
            tooltip=["Database", "Criterion", "Score"],
        )
        .properties(height=320)
        .configure(background="transparent")
        .configure_view(strokeWidth=0)
        .configure_axis(labelColor="#e6ebf3", gridColor="rgba(148,180,255,0.12)")
        .configure_legend(labelColor="#e6ebf3", titleColor="#8d9bb0")
    )
    stretch(st.altair_chart, chart)


BEST_FOR = {
    "Vector search and RAG": {"Vector Search": 10, "AI Integration": 8, "Latency": 7, "Scalability": 6},
    "Transactions and consistency": {"Transactions": 10, "Security": 8, "Availability": 8},
    "Low latency at scale": {"Latency": 10, "Scalability": 9, "Availability": 7},
    "Budget friendly": {"Cost": 10, "Availability": 5, "Latency": 5, "Security": 5},
}


def best_for_cards(caps):
    cols = st.columns(len(BEST_FOR))
    for col, (label, imp) in zip(cols, BEST_FOR.items()):
        try:
            res = analyze(caps, imp, runs=20)["wsm"]
        except Exception:
            continue
        runners = ", ".join(res.index[1:3])
        col.markdown(
            f'<div class="pick"><div class="k">Best for</div><div class="n">{html.escape(label)}</div>'
            f'<div><b>{html.escape(res.index[0])}</b> <span class="s">{res.iloc[0]:.1f}</span></div>'
            f'<div class="r">Then {html.escape(runners)}</div></div>',
            unsafe_allow_html=True,
        )


def importance_from(requirements):
    return {
        label: requirements[field]
        for field, label in CRITERION_MAPPING.items()
        if requirements.get(field) is not None
    }


def build_report(description, requirements, rankings, analysis):
    imp = importance_from(requirements)
    top = rankings[0]
    sens = analysis["sensitivity"]
    lines = [
        "# Database recommendation",
        "",
        f"**Application:** {requirements['application_type']}",
        f"**Expected users:** {requirements['expected_users']:,}" if requirements["expected_users"] is not None else "**Expected users:** not specified",
        "",
        "## Description",
        description.strip(),
        "",
        "## Priorities (1-10)",
        *[f"- {label}: {value}" for label, value in imp.items()],
        "",
        "## Ranking (Weighted Sum Model)",
        "| Rank | Database | Score / 10 | TOPSIS |",
        "|---|---|---|---|",
    ]
    for i, item in enumerate(rankings, start=1):
        t = analysis["topsis"].get(item["database_name"])
        lines.append(f"| {i} | {item['database_name']} | {item['score']:.2f} | {t:.3f} |" if t is not None else f"| {i} | {item['database_name']} | {item['score']:.2f} | - |")
    p_first = float(sens["p_first"].get(top["database_name"], 0))
    lines += [
        "",
        f"**Best match:** {top['database_name']} ({top['score']:.2f}/10), first in {p_first:.0%} of 500 weight-perturbation runs (+/-30%).",
        "",
        "## Critical gaps (importance >= 8, score <= 5)",
    ]
    any_gap = False
    for name in [r["database_name"] for r in rankings[:5]]:
        for criterion, score, importance in analysis["gaps"].get(name, []):
            any_gap = True
            lines.append(f"- {name}: {criterion} scored {score:.0f} against importance {importance:.0f}")
    if not any_gap:
        lines.append("- None among the top five.")
    lines += ["", "Scores are qualitative suitability ratings based on public documentation. Validate with your own workload tests."]
    return "\n".join(lines)


# =========================================================
# NAVIGATION
# =========================================================

PAGES = [
    "Overview",
    "Find a Database",
    "Compare Databases",
    "Database Explorer",
    "Schema Designer",
    "History",
]


def go_to_page(page_name):
    st.session_state["nav_page"] = page_name


def go_design_with(text):
    st.session_state["design_description"] = text
    st.session_state["nav_page"] = "Schema Designer"


if "nav_page" not in st.session_state:
    st.session_state["nav_page"] = "Overview"

if "flash" in st.session_state:
    st.toast(st.session_state.pop("flash"))


# =========================================================
# DATABASE HELPERS
# =========================================================

@contextmanager
def db():
    """Connection that commits on success and is always closed."""
    conn = get_connection()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def read_query(query, params=None):
    with db() as conn:
        return pd.read_sql_query(query, conn, params=params)


def get_databases():
    return read_query(
        """
        SELECT database_id, name, database_type, description, created_at
        FROM database_systems
        WHERE is_active = TRUE
        ORDER BY name;
        """
    )


def get_criteria():
    df = read_query(
        """
        SELECT criterion_id, name, description, weight
        FROM criteria
        ORDER BY criterion_id;
        """
    )
    df["weight"] = df["weight"].astype(float)
    return df


def get_capabilities(database_ids=None):
    query = """
        SELECT
            ds.database_id,
            ds.name AS database_name,
            ds.database_type,
            ds.description AS database_description,
            c.criterion_id,
            c.name AS criterion,
            c.description AS criterion_description,
            c.weight,
            dcs.score,
            dcs.evidence,
            dcs.reasoning,
            dcs.source_url,
            dcs.origin
        FROM database_systems ds
        JOIN database_criteria_scores dcs
            ON dcs.database_id = ds.database_id
        JOIN criteria c
            ON c.criterion_id = dcs.criterion_id
        WHERE ds.is_active = TRUE
    """
    params = None

    if database_ids:
        query += " AND ds.database_id = ANY(%s)"
        # Plain ints: psycopg2 cannot adapt numpy.int64.
        params = ([int(i) for i in database_ids],)

    query += " ORDER BY ds.name, c.criterion_id"
    df = read_query(query, params)
    df["score"] = df["score"].astype(float)
    df["weight"] = df["weight"].astype(float)
    return df


def get_history():
    return read_query(
        """
        SELECT
            a.application_id,
            a.application_type,
            a.description,
            a.expected_users,
            a.created_at,
            COUNT(r.recommendation_id) AS recommendation_count
        FROM applications a
        LEFT JOIN recommendations r
            ON r.application_id = a.application_id
            AND r.method = 'WSM'
        GROUP BY
            a.application_id,
            a.application_type,
            a.description,
            a.expected_users,
            a.created_at
        ORDER BY a.created_at DESC;
        """
    )


def save_profile(profile):
    """Insert or refresh a researched profile (see llm.database_profiler) in one transaction."""

    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO database_systems (name, database_type, description)
                VALUES (%s, %s, %s)
                ON CONFLICT (name) DO UPDATE
                SET database_type = EXCLUDED.database_type,
                    description = EXCLUDED.description,
                    is_active = TRUE
                RETURNING database_id;
                """,
                (
                    profile["name"].strip(),
                    profile["database_type"],
                    profile["description"].strip(),
                ),
            )
            database_id = cur.fetchone()[0]

            for rating in profile["ratings"]:
                cur.execute(
                    """
                    INSERT INTO database_criteria_scores
                        (database_id, criterion_id, score, evidence, reasoning, source_url, origin, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (database_id, criterion_id) DO UPDATE
                    SET score = EXCLUDED.score,
                        evidence = EXCLUDED.evidence,
                        reasoning = EXCLUDED.reasoning,
                        source_url = EXCLUDED.source_url,
                        origin = EXCLUDED.origin,
                        updated_at = CURRENT_TIMESTAMP;
                    """,
                    (
                        database_id,
                        int(rating["criterion_id"]),
                        int(rating["score"]),
                        rating.get("evidence", ""),
                        rating.get("reasoning") or rating.get("evidence", ""),
                        rating.get("source_url") or None,
                        "web" if profile.get("used_web") else "model",
                    ),
                )

    return database_id


def deactivate_database(database_id):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE database_systems SET is_active = FALSE WHERE database_id = %s;",
                (int(database_id),),
            )


def research(name, criteria_df):
    return profile_database(
        name, criteria_df[["criterion_id", "name", "description"]].to_dict("records")
    )


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:
    st.markdown(
        """
        <div style="padding: 0.4rem 0 0.8rem;">
            <div class="brand">DB<span>.</span>Selector</div>
            <div class="brand-sub">Pick the right database, show your work.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    page = st.radio(
        "Navigation",
        PAGES,
        key="nav_page",
        label_visibility="collapsed",
    )


# =========================================================
# OVERVIEW
# =========================================================

if page == "Overview":
    st.markdown(
        """
        <div class="hero">
            <span class="pill">Decision support</span>
            <h1>Choose the right database, with the reasoning shown.</h1>
            <p class="lede">Describe your workload in plain English. Requirements are extracted,
            every candidate is scored, and the ranking is stress-tested so you can see how
            confident the answer really is.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        databases = get_databases()
        history = get_history()
        criteria = get_criteria()
        caps = get_capabilities()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Databases in catalog", len(databases))
        col2.metric("Evaluation criteria", len(criteria))
        col3.metric("Database types", databases["database_type"].nunique())
        col4.metric("Saved analyses", len(history))

        st.write("")
        left, middle, right = st.columns(3)

        with left:
            with st.container(border=True):
                st.markdown("#### Find a database")
                st.write("Describe your application and get a ranked, stress-tested shortlist.")
                stretch(st.button, "Start an analysis", key="overview_find", type="primary",
                        on_click=go_to_page, args=("Find a Database",))

        with middle:
            with st.container(border=True):
                st.markdown("#### Compare databases")
                st.write("Put candidates side by side with a heatmap and per-criterion winners.")
                stretch(st.button, "Open comparison", key="overview_compare",
                        on_click=go_to_page, args=("Compare Databases",))

        with right:
            with st.container(border=True):
                st.markdown("#### Design the schema")
                st.write("Turn an app idea into PostgreSQL tables and class diagrams.")
                stretch(st.button, "Open the designer", key="overview_design",
                        on_click=go_to_page, args=("Schema Designer",))

        st.write("")
        if not caps.empty:
            st.subheader("Best picks by use case")
            best_for_cards(caps)
            st.write("")

        st.subheader("Catalog at a glance")

        if caps.empty:
            st.info("The catalog has no scores yet. Run `python -m database.seed_catalog`.")
        else:
            order = criteria["name"].tolist()
            wide = caps.pivot_table(index="database_name", columns="criterion", values="score", aggfunc="first")
            wide = wide.reindex(columns=[c for c in order if c in wide.columns])
            wide.index.name = "Database"
            heatmap(wide)
            st.caption(
                "Qualitative 1-10 suitability ratings (higher is better; for Cost, 10 is cheapest) "
                "with a source link per score in the Database Explorer."
            )

        st.subheader("Database catalog")
        stretch(st.dataframe, databases[["name", "database_type", "description"]], hide_index=True)

    except Exception as exc:
        st.error(f"Could not load the dashboard: {exc}")


# =========================================================
# FIND A DATABASE
# =========================================================

elif page == "Find a Database":
    page_header(
        "Find your database.",
        "Describe what you are building. Requirements are extracted, every candidate is "
        "scored two ways, and the winner is stress-tested.",
    )

    FIND_EXAMPLES = {
        "RAG chatbot": (
            "I'm building a RAG chatbot for 50,000 users. Fast vector search, "
            "high scalability, and affordability are critical."
        ),
        "Payments ledger": (
            "Payments ledger for a fintech app with 200000 users. Strict transactions "
            "and consistency, strong security, and high availability are essential."
        ),
        "IoT telemetry": (
            "IoT platform ingesting huge volumes of sensor data. It needs massive "
            "storage capacity, low cost, and very high scalability."
        ),
        "Product catalog": (
            "E-commerce product catalog with fast search, flexible product data, "
            "low latency and good availability for around 1 million users."
        ),
    }

    def use_find_example(text):
        st.session_state["find_description"] = text

    st.markdown("**Start from an example**")
    example_cols = st.columns(len(FIND_EXAMPLES))
    for column, (label, text) in zip(example_cols, FIND_EXAMPLES.items()):
        with column:
            stretch(st.button, label, key=f"find_ex_{label}", on_click=use_find_example, args=(text,))

    with st.form("recommendation_form"):
        description = st.text_area(
            "Application description",
            key="find_description",
            height=155,
            placeholder="What are you building, who uses it, and what matters most?",
        )
        submitted = stretch(st.form_submit_button, "Run database analysis", type="primary")

    if submitted:
        if not description.strip():
            st.warning("Describe your application first.")
        else:
            try:
                with st.spinner("Extracting requirements..."):
                    raw = extract_requirements(description)
                    requirements = validate_requirements(raw)

                with st.spinner("Saving and ranking..."):
                    application_id = save_application(description, requirements)
                    rankings = recommend(application_id)

                st.session_state["requirements"] = requirements
                st.session_state["rankings"] = rankings
                st.session_state["application_id"] = application_id
                st.session_state["find_text"] = description.strip()
                st.success(f"Analysis complete. Saved as application #{application_id}.")

            except ValueError as exc:
                st.error(
                    f"The requirements could not be used: {exc}. "
                    "Try adding detail about speed, scale, cost or security."
                )
            except Exception as exc:
                st.error(f"Recommendation failed: {exc}")

    if "rankings" in st.session_state:
        requirements = st.session_state["requirements"]
        rankings = st.session_state["rankings"]
        text_used = st.session_state.get("find_text", "")
        importance = importance_from(requirements)

        try:
            caps_all = get_capabilities()
            analysis = analyze(caps_all, importance)
        except Exception as exc:
            st.error(f"Could not analyse the result: {exc}")
            st.stop()

        winner = rankings[0]
        sens = analysis["sensitivity"]
        p_first = float(sens["p_first"].get(winner["database_name"], 0.0))
        topsis_top = analysis["topsis"].index[0]
        agree = topsis_top == winner["database_name"]

        st.divider()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Best match", winner["database_name"])
        col2.metric("Weighted score", f'{winner["score"]:.2f} / 10')
        col3.metric("Confidence", f"{p_first:.0%}", help="Share of 500 runs, with every priority shifted randomly by up to 30%, in which this database still ranks first.")
        col4.metric("TOPSIS agrees", "Yes" if agree else f"No ({topsis_top})")

        if p_first < 0.5:
            callout("The top spot is not stable: small changes in priorities change the winner. Compare the top candidates in the Robustness tab.", "warn")
        elif agree and p_first >= 0.8:
            callout("Both ranking methods agree and the winner holds up under changed priorities.", "good")

        gap_list = analysis["gaps"].get(winner["database_name"], [])
        if gap_list:
            callout(
                f'{winner["database_name"]} is weak on a critical need: '
                + ", ".join(f"{c} (score {s:.0f}, importance {i:.0f})" for c, s, i in gap_list),
                "warn",
            )

        tab_rank, tab_break, tab_trade, tab_robust, tab_what = st.tabs(
            ["Ranking", "Breakdown", "Trade-offs", "Robustness", "What-if"]
        )

        with tab_rank:
            ranking_bars(rankings)

            requirement_df = pd.DataFrame(
                [{"Criterion": label, "Importance": requirements[field]} for field, label in CRITERION_MAPPING.items()]
            )
            requirement_df["Importance"] = pd.to_numeric(requirement_df["Importance"], errors="coerce")

            st.subheader("What you asked for")
            stretch(
                st.dataframe,
                requirement_df,
                hide_index=True,
                column_config={
                    "Importance": st.column_config.ProgressColumn(
                        "Importance", min_value=0, max_value=10, format="%d / 10",
                        help="Blank means the description did not mention it.",
                    )
                },
            )
            users = requirements["expected_users"]
            st.caption(
                f'Application type: {requirements["application_type"]}. '
                f'Expected users: {users:,}' if users is not None else
                f'Application type: {requirements["application_type"]}. Expected users: not specified.'
            )

            report = build_report(text_used, requirements, rankings, analysis)
            st.download_button("Download report (Markdown)", data=report, file_name="database_recommendation.md", mime="text/markdown", key="dl_report")
            st.button("Design a schema for this application", on_click=go_design_with, args=(text_used,), key="find_to_design")

        with tab_break:
            names = [r["database_name"] for r in rankings]
            top_n = names[:6]
            st.subheader("Weighted contribution to the final score")
            contrib = contributions(analysis["matrix"], analysis["weights"]).loc[top_n]
            contrib.index.name = "Database"
            heatmap(contrib, fmt=".2f", domain=(0, float(contrib.max().max())))

            st.subheader(f"Why {winner['database_name']} instead of...")
            rivals = [n for n in names if n != winner["database_name"]]
            rival = st.selectbox("Compare the winner with", rivals, key="rival_pick")
            m = analysis["matrix"]
            w = analysis["weights"]
            diff = pd.DataFrame(
                {
                    "Criterion": m.columns,
                    "Importance": [importance[c] for c in m.columns],
                    winner["database_name"]: m.loc[winner["database_name"]].values,
                    rival: m.loc[rival].values,
                }
            )
            diff["Weighted advantage"] = (diff[winner["database_name"]] - diff[rival]) * w.values
            stretch(st.dataframe, diff.sort_values("Weighted advantage", ascending=False), hide_index=True)
            st.caption("Positive advantage favours the winner. Values sum to the score gap between the two.")

            st.subheader("Evidence for the winner")
            ev = caps_all[caps_all["database_name"] == winner["database_name"]]
            score_cards(ev[ev["criterion"].isin(importance)])

        with tab_trade:
            st.write("Databases that score 5 or below on a criterion you rated 8 or higher.")
            shown = 0
            for r in rankings[:6]:
                gl = analysis["gaps"].get(r["database_name"], [])
                label = f'{r["database_name"]}: {len(gl)} critical gap(s)' if gl else f'{r["database_name"]}: no critical gaps'
                with st.expander(label, expanded=bool(gl) and shown < 2):
                    if gl:
                        shown += 1
                        stretch(st.dataframe, pd.DataFrame(gl, columns=["Criterion", "Score", "Importance"]), hide_index=True)
                    else:
                        st.write("Meets every high-priority requirement.")
            clean = [r for r in rankings if not analysis["gaps"].get(r["database_name"])]
            if clean and clean[0]["database_name"] != winner["database_name"]:
                callout(
                    f'Highest-ranked database with no critical gaps: {clean[0]["database_name"]} '
                    f'({clean[0]["score"]:.2f}/10).', "good",
                )

        with tab_robust:
            st.write("Priorities were shifted randomly by up to 30% across 500 runs.")
            table = sens.head(8).rename(
                columns={"p_first": "Ranks first", "p_top3": "In top 3", "avg_rank": "Average rank",
                         "best_rank": "Best rank", "worst_rank": "Worst rank"}
            )
            stretch(
                st.dataframe,
                table,
                column_config={
                    "Ranks first": st.column_config.ProgressColumn("Ranks first", min_value=0, max_value=1, format="percent"),
                    "In top 3": st.column_config.ProgressColumn("In top 3", min_value=0, max_value=1, format="percent"),
                    "Average rank": st.column_config.NumberColumn(format="%.2f"),
                },
            )
            tt = analysis["topsis"].head(6).rename("TOPSIS closeness").to_frame()
            st.subheader("TOPSIS cross-check")
            stretch(st.bar_chart, tt)
            st.caption("TOPSIS scores each option by its distance from the best and worst possible profile. Agreement with the weighted sum raises confidence.")

        with tab_what:
            st.write("Adjust priorities and re-rank instantly. Nothing here is saved. Set a slider to 0 to ignore a criterion.")
            what_if = {}
            cols = st.columns(3)
            for i, (field, label) in enumerate(CRITERION_MAPPING.items()):
                with cols[i % 3]:
                    what_if[label] = st.slider(label, 0, 10, int(importance.get(label, 0)), key=f"whatif_{field}")
            if any(what_if.values()):
                try:
                    alt_analysis = analyze(caps_all, what_if, runs=50)
                    ranking_bars(
                        [{"database_name": n, "score": float(s)} for n, s in alt_analysis["wsm"].head(8).items()]
                    )
                except Exception as exc:
                    st.warning(f"Could not re-rank: {exc}")
            else:
                st.info("Give at least one criterion an importance above zero.")

        st.caption("Scores are qualitative suitability ratings based on public documentation. Validate the shortlist with your own workload tests.")


# =========================================================
# COMPARE DATABASES
# =========================================================

elif page == "Compare Databases":
    page_header(
        "Compare your candidates.",
        "Pick two or more databases to see scores side by side, the winner per criterion, and the evidence.",
    )

    try:
        databases = get_databases()
        criteria = get_criteria()

        if databases.empty:
            st.warning("No active databases are available.")
        else:
            name_to_id = {n: int(i) for n, i in zip(databases["name"], databases["database_id"])}
            defaults = [n for n in ("PostgreSQL", "MongoDB", "Qdrant") if n in name_to_id] or list(name_to_id)[:2]

            selected_names = st.multiselect("Databases to compare", options=list(name_to_id), default=defaults)

            if len(selected_names) < 2:
                st.info("Choose at least two databases to compare.")
            else:
                data = get_capabilities([name_to_id[n] for n in selected_names])

                if data.empty:
                    st.warning("No capability scores were found.")
                else:
                    order = [c for c in criteria["name"] if c in set(data["criterion"])]
                    pivot = data.pivot_table(index="database_name", columns="criterion", values="score", aggfunc="first")[order]
                    pivot = pivot.loc[selected_names]
                    pivot.index.name = "Database"

                    weights = criteria.set_index("name")["weight"]
                    overall = (pivot * weights[order]).sum(axis=1) / weights[order].sum()
                    best = overall.idxmax()

                    c1, c2 = st.columns(2)
                    c1.metric("Best overall (default weights)", best, f"{overall.max():.2f} / 10")
                    c2.metric("Databases compared", len(selected_names))

                    st.subheader("Heatmap")
                    heatmap(pivot)

                    st.subheader("Winner per criterion")
                    winners = pd.DataFrame(
                        {
                            "Criterion": order,
                            "Best": [", ".join(pivot.index[pivot[c] == pivot[c].max()]) for c in order],
                            "Score": [pivot[c].max() for c in order],
                            "Spread": [pivot[c].max() - pivot[c].min() for c in order],
                        }
                    )
                    stretch(st.dataframe, winners, hide_index=True)

                    st.subheader("Criterion by criterion")
                    grouped_bars(pivot)

                    st.subheader("Overall score with default criterion weights")
                    stretch(st.bar_chart, overall.rename("Score").to_frame())

                    st.subheader("Evidence behind each score")
                    for name in selected_names:
                        with st.expander(name):
                            db_data = data[data["database_name"] == name]
                            desc = db_data["database_description"].dropna()
                            st.write(desc.iloc[0] if not desc.empty else "No description supplied.")
                            score_cards(db_data)

                    st.caption("This page shows recorded catalog ratings; it does not calculate workload-specific scores. Use Find a Database for that.")

    except Exception as exc:
        st.error(f"Comparison failed: {exc}")


# =========================================================
# DATABASE EXPLORER
# =========================================================

elif page == "Database Explorer":
    page_header(
        "Explore the catalog.",
        "Browse databases and their evidence, add a new one by name, or refresh its scores from the web.",
    )

    try:
        databases = get_databases()
        criteria = get_criteria()

        tab_browse, tab_add, tab_manage = st.tabs(["Browse", "Add a database", "Refresh and remove"])

        with tab_browse:
            f1, f2 = st.columns([2, 1])
            search = f1.text_input("Search the catalog", placeholder="Search by name, type or description")
            types = sorted(databases["database_type"].unique())
            type_filter = f2.multiselect("Type", types)

            filtered = databases.copy()
            if search.strip():
                mask = False
                for column in ("name", "database_type", "description"):
                    mask = mask | filtered[column].fillna("").str.contains(search, case=False, regex=False)
                filtered = filtered[mask]
            if type_filter:
                filtered = filtered[filtered["database_type"].isin(type_filter)]

            if not filtered.empty:
                caps_all = get_capabilities(filtered["database_id"].tolist())
                cards = []
                for _, drow in filtered.iterrows():
                    own = caps_all[caps_all["database_id"] == drow["database_id"]].sort_values("score", ascending=False)
                    chips = "".join(
                        f'<span class="tag hot">{html.escape(c)} {s:.0f}</span>'
                        for c, s in zip(own["criterion"].head(3), own["score"].head(3))
                    )
                    cards.append(
                        '<div class="db-card">'
                        f'<span class="tag">{html.escape(str(drow["database_type"]))}</span>'
                        f'<h4>{html.escape(drow["name"])}</h4>'
                        f'<p>{html.escape(str(drow["description"] or ""))}</p>'
                        f'<div class="db-strengths">{chips}</div></div>'
                    )
                st.markdown(f'<div class="db-grid">{"".join(cards)}</div>', unsafe_allow_html=True)
            else:
                st.info("No databases match these filters.")

            if not filtered.empty:
                pick = st.selectbox("Inspect a database", filtered["name"].tolist(), key="inspect_db")
                row = filtered[filtered["name"] == pick].iloc[0]
                caps = get_capabilities([row["database_id"]])
                st.write(row["description"])
                score_cards(caps)

        with tab_add:
            st.write("Type a database name. It is researched online and scored on every criterion automatically.")

            if st.session_state.pop("clear_new_db", False):
                st.session_state["new_db_name"] = ""

            new_name = st.text_input("Database name", key="new_db_name", placeholder="e.g. TimescaleDB", max_chars=60)
            add_clicked = stretch(st.button, "Research and add to catalog", key="add_db_button", type="primary")

            if add_clicked:
                clean_name = new_name.strip()
                existing = {n.lower() for n in databases["name"]}

                if not clean_name:
                    st.error("Enter a database name.")
                elif criteria.empty:
                    st.error("No evaluation criteria are configured.")
                elif clean_name.lower() in existing:
                    st.error(f"{clean_name} is already in the catalog.")
                else:
                    try:
                        with st.spinner(f"Researching {clean_name} online. This can take a minute..."):
                            profile = research(clean_name, criteria)

                        if profile["name"].lower() in existing:
                            st.error(f'{profile["name"]} is already in the catalog.')
                        else:
                            database_id = save_profile(profile)
                            st.session_state["last_added"] = profile
                            st.session_state["clear_new_db"] = True
                            st.session_state["flash"] = f'Added {profile["name"]} to the catalog (ID {database_id}).'
                            st.rerun()

                    except (ValueError, RuntimeError) as exc:
                        st.error(str(exc))
                    except Exception as exc:
                        st.error(f"Could not add the database. Details: {exc}")

            last_added = st.session_state.get("last_added")
            if last_added:
                with st.expander(f'Last added: {last_added["name"]}', expanded=True):
                    st.write(f'**Type:** {last_added["database_type"]}')
                    st.write(last_added["description"])
                    if not last_added["used_web"]:
                        st.warning("Live web search was unavailable, so these scores are model estimates.")
                    score_cards(
                        pd.DataFrame(last_added["ratings"]).assign(
                            origin="web" if last_added["used_web"] else "model"
                        )
                    )
                    if last_added["sources"]:
                        st.caption("Sources found: " + ", ".join(last_added["sources"]))

        with tab_manage:
            if databases.empty:
                st.info("The catalog is empty.")
            else:
                target = st.selectbox("Database", databases["name"].tolist(), key="manage_db")
                row = databases[databases["name"] == target].iloc[0]

                m1, m2 = st.columns(2)

                with m1:
                    with st.container(border=True):
                        st.markdown("#### Refresh scores")
                        st.write("Re-research this database online and replace its scores and evidence.")
                        if stretch(st.button, "Re-research now", key="refresh_db"):
                            try:
                                with st.spinner(f"Researching {target}..."):
                                    profile = research(target, criteria)
                                    profile["name"] = target
                                    save_profile(profile)
                                st.session_state["flash"] = f"Refreshed {target}."
                                st.rerun()
                            except (ValueError, RuntimeError) as exc:
                                st.error(str(exc))
                            except Exception as exc:
                                st.error(f"Refresh failed: {exc}")

                with m2:
                    with st.container(border=True):
                        st.markdown("#### Remove from catalog")
                        st.write("Removed databases stop appearing in rankings. Past analyses keep their results.")
                        confirm = st.checkbox(f"Remove {target}", key="confirm_remove")
                        if stretch(st.button, "Remove", key="remove_db", disabled=not confirm):
                            deactivate_database(row["database_id"])
                            st.session_state["flash"] = f"Removed {target}."
                            st.rerun()

    except Exception as exc:
        st.error(f"Could not load the catalog: {exc}")


# =========================================================
# SCHEMA DESIGNER
# =========================================================

elif page == "Schema Designer":
    page_header(
        "Design the schema.",
        "Describe your application and get PostgreSQL tables, SQL, and a class "
        "diagram to start from. Nothing is ever executed against your database.",
    )

    EXAMPLES = {
        "Library system": "Library management system with books, authors, members, loans, due dates and return tracking.",
        "Online store": "Online store with customers, products, categories, orders, order items and payments.",
        "Clinic booking": "Clinic appointment system with patients, doctors, appointments, and prescriptions.",
        "Course platform": "Online course platform with instructors, students, courses, lessons, enrollments and progress tracking.",
    }

    def use_example(text):
        st.session_state["design_description"] = text

    if generate_database_design is None:
        st.error(
            "The schema designer module could not be loaded. "
            f"{DESIGNER_ERROR} Save database_designer.py next to app.py or under llm/."
        )
    else:
        st.markdown("**Start from an example**")
        example_cols = st.columns(len(EXAMPLES))
        for column, (label, text) in zip(example_cols, EXAMPLES.items()):
            with column:
                stretch(st.button, label, key=f"example_{label}", on_click=use_example, args=(text,))

        design_description = st.text_area(
            "Application description",
            key="design_description",
            height=140,
            max_chars=2000,
            placeholder="What does the application do, and what data does it keep track of?",
        )

        generate = stretch(st.button, "Generate schema", key="generate_design", type="primary")

        if generate:
            if not design_description.strip():
                st.warning("Describe your application first.")
            else:
                try:
                    with st.spinner("Designing tables and classes..."):
                        st.session_state["design"] = generate_database_design(design_description)
                        st.session_state["design_source"] = design_description.strip()
                except RuntimeError as exc:
                    st.error(f"The model call failed: {exc}")
                except ValueError as exc:
                    st.error(f"The model returned an unusable design: {exc}")
                except Exception as exc:
                    st.error(f"Schema generation failed: {exc}")

        design = st.session_state.get("design")

        if design:
            st.divider()
            st.subheader(design["application_name"])

            col1, col2, col3 = st.columns(3)
            col1.metric("Tables", len(design["tables"]))
            col2.metric("Classes", len(design["classes"]))
            col3.metric("Relationships", len(design.get("relationships", [])))

            tab_tables, tab_sql, tab_classes, tab_notes = st.tabs(
                ["Tables", "SQL", "Classes and diagram", "Notes"]
            )

            with tab_tables:
                for table in design["tables"]:
                    with st.expander(f'{table["name"]}: {table.get("purpose", "")}'):
                        columns_df = pd.DataFrame(table["columns"]).rename(
                            columns={"name": "Column", "type": "Type", "constraints": "Constraints"}
                        )
                        stretch(st.dataframe, columns_df, hide_index=True)

            with tab_sql:
                st.code(design["sql"], language="sql")
                st.download_button("Download schema.sql", data=design["sql"], file_name="schema.sql", mime="text/plain", key="download_sql")
                st.caption("Review the SQL before running it. This app never executes it.")

            with tab_classes:
                st.subheader("UML class diagram")
                render_mermaid(design["class_diagram"])

                with st.expander("View Mermaid source"):
                    st.code(design["class_diagram"], language="text")

                st.subheader("Class details")
                for cls in design["classes"]:
                    with st.expander(f'Class: {cls["name"]}'):
                        left, right = st.columns(2)
                        with left:
                            st.markdown("**Attributes**")
                            for attribute in cls.get("attributes", []):
                                st.code(str(attribute), language="text")
                        with right:
                            st.markdown("**Methods**")
                            for method in cls.get("methods", []):
                                st.code(str(method), language="text")

            with tab_notes:
                st.markdown("**Relationships**")
                for relationship in design.get("relationships", []):
                    st.markdown(f"- {relationship}")

                st.markdown("**Design notes**")
                for note in design.get("design_notes", []):
                    st.markdown(f"- {note}")

                st.download_button("Download full design (JSON)", data=json.dumps(design, indent=2), file_name="database_design.json", mime="application/json", key="download_json")


# =========================================================
# HISTORY
# =========================================================

elif page == "History":
    page_header(
        "Your analysis history.",
        "Reopen earlier applications, re-rank them against the current catalog, or export them.",
    )

    try:
        history = get_history()

        if history.empty:
            st.info("Nothing saved yet. Run an analysis in Find a Database.")
        else:
            shown = history.rename(
                columns={
                    "application_id": "ID", "application_type": "Application", "description": "Description",
                    "expected_users": "Expected users", "created_at": "Created", "recommendation_count": "Saved rankings",
                }
            )
            stretch(st.dataframe, shown, hide_index=True)
            st.download_button("Download history (CSV)", data=shown.to_csv(index=False), file_name="analysis_history.csv", mime="text/csv", key="dl_history")

            type_by_id = dict(zip(history["application_id"], history["application_type"]))

            selected_id = st.selectbox(
                "Inspect an application",
                options=[int(v) for v in history["application_id"]],
                format_func=lambda value: f"#{value}: {type_by_id.get(value, '')}",
            )

            with db() as conn:
                details = pd.read_sql_query(
                    "SELECT application_type, description, expected_users, created_at FROM applications WHERE application_id = %s;",
                    conn, params=(selected_id,),
                )
                saved_rankings = pd.read_sql_query(
                    """
                    SELECT r.rank, ds.name AS database_name, r.score, r.explanation, r.created_at
                    FROM recommendations r
                    JOIN database_systems ds ON ds.database_id = r.database_id
                    WHERE r.application_id = %s AND r.method = 'WSM'
                    ORDER BY r.rank;
                    """,
                    conn, params=(selected_id,),
                )
                req_rows = pd.read_sql_query(
                    """
                    SELECT c.name AS criterion, ar.importance
                    FROM application_requirements ar
                    JOIN criteria c ON c.criterion_id = ar.criterion_id
                    WHERE ar.application_id = %s
                    ORDER BY c.criterion_id;
                    """,
                    conn, params=(selected_id,),
                )

            if not details.empty:
                app_row = details.iloc[0]
                st.subheader("Application")
                st.write(app_row["description"])
                st.caption(
                    "Expected users: "
                    + (f'{int(app_row["expected_users"]):,}' if pd.notna(app_row["expected_users"]) else "Not specified")
                )

            if not req_rows.empty:
                req_rows["importance"] = req_rows["importance"].astype(float)
                stretch(
                    st.dataframe,
                    req_rows.rename(columns={"criterion": "Criterion", "importance": "Importance"}),
                    hide_index=True,
                    column_config={"Importance": st.column_config.ProgressColumn("Importance", min_value=0, max_value=10, format="%d / 10")},
                )

            st.subheader("Saved rankings")

            if saved_rankings.empty:
                st.info("No saved WSM rankings for this application.")
            else:
                ranking_bars(
                    [{"database_name": r["database_name"], "score": float(r["score"])} for _, r in saved_rankings.iterrows()]
                )
                with st.expander("Full table"):
                    stretch(
                        st.dataframe,
                        saved_rankings.rename(
                            columns={"rank": "Rank", "database_name": "Database", "score": "Score", "explanation": "Explanation", "created_at": "Created"}
                        ),
                        hide_index=True,
                    )

            def rerank(app_id):
                try:
                    recommend(app_id)
                    st.session_state["flash"] = f"Re-ranked application #{app_id} against the current catalog."
                except Exception as exc:
                    st.session_state["flash"] = f"Re-rank failed: {exc}"

            st.button("Re-rank against the current catalog", key="rerank", on_click=rerank, args=(selected_id,))

    except Exception as exc:
        st.error(f"Could not load history: {exc}")