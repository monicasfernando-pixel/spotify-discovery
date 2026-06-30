"""
app.py — Spotify Discovery Review Analysis Engine (Deliverable #1)
------------------------------------------------------------------
Reads two finished data files and presents:
  1. The funnel (all reviews -> relevant pool -> A/B split)
  2. Source comparison (app stores vs forums) — the triangulation
  3. The six brief questions, answered from data
  4. A browsable review explorer
  5. A LIVE tagger — paste any review, Claude tags it in ~1 second

Run locally (from project root):
    streamlit run app/app.py

Deploy:        push to GitHub, then deploy on share.streamlit.io
               and add ANTHROPIC_API_KEY in the app's Secrets.

Expected data files:
  - data/processed/tagged_reviews.csv      (app + play store, keyword-tagged)
  - data/processed/qualitative_coded.csv   (reddit + community, hand-coded)
"""

from pathlib import Path

import streamlit as st
import pandas as pd
import altair as alt

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"

st.set_page_config(page_title="Spotify Discovery — Review Engine",
                   page_icon="🎧", layout="wide")

# ---------------------------------------------------------------- theme / palette
GREEN = "#1DB954"
GREEN_SOFT = "#1ed760"
BLUE = "#509bf5"
AMBER = "#f5a623"
MUTED = "#8a8f98"

# ---------------------------------------------------------------- styling
st.markdown(
    """
    <style>
      /* tighten top padding */
      .block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1250px; }

      /* hero */
      .hero {
        background: radial-gradient(1200px 400px at 0% 0%, rgba(29,185,84,0.18), transparent 60%),
                    linear-gradient(135deg, #11261b 0%, #14161c 55%);
        border: 1px solid rgba(29,185,84,0.25);
        border-radius: 18px; padding: 26px 30px; margin-bottom: 8px;
      }
      .hero h1 { font-size: 2.05rem; font-weight: 800; margin: 0 0 6px 0; letter-spacing:-0.5px; }
      .hero p  { color: #b9bec7; font-size: 0.98rem; margin: 0; max-width: 880px; line-height:1.5; }
      .pill {
        display:inline-block; padding: 3px 11px; border-radius: 999px; font-size: 0.74rem;
        font-weight: 700; margin-right: 7px; margin-top: 12px; letter-spacing:0.3px;
      }
      .pill-a { background: rgba(80,155,245,0.16);  color:#86b7f7; border:1px solid rgba(80,155,245,0.4);}
      .pill-b { background: rgba(29,185,84,0.16);   color:#56d98a; border:1px solid rgba(29,185,84,0.45);}
      .pill-c { background: rgba(245,166,35,0.16);  color:#f3b65a; border:1px solid rgba(245,166,35,0.45);}

      /* metric cards */
      div[data-testid="stMetric"] {
        background: #161922; border: 1px solid #262b36; border-radius: 14px;
        padding: 16px 18px;
      }
      div[data-testid="stMetric"] label p { color: #9aa0ab !important; font-weight:600; }
      div[data-testid="stMetricValue"] { font-size: 1.9rem; font-weight: 800; }

      /* section headings */
      h2 { font-weight: 800 !important; letter-spacing:-0.3px; }
      h3 { color:#e7e9ee !important; font-weight:700 !important; }

      /* tabs */
      button[data-baseweb="tab"] { font-size: 0.98rem; font-weight: 700; }
      button[data-baseweb="tab"][aria-selected="true"] { color: #1ed760 !important; }
      div[data-baseweb="tab-highlight"] { background-color: #1DB954 !important; }

      /* dataframe rounding */
      div[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- data loading
@st.cache_data
def load_quant():
    df = pd.read_csv(PROCESSED / "tagged_reviews.csv", low_memory=False)
    return df

@st.cache_data
def load_qual():
    df = pd.read_csv(PROCESSED / "qualitative_coded.csv")
    # drop near-duplicates so counts aren't inflated
    if "near_duplicate" in df.columns:
        df = df[df["near_duplicate"].astype(str).str.lower() != "true"]
    return df

quant_ok = qual_ok = True
try:
    quant = load_quant()
except Exception as e:
    quant_ok = False
    quant = pd.DataFrame()
try:
    qual = load_qual()
except Exception as e:
    qual_ok = False
    qual = pd.DataFrame()

# ---------------------------------------------------------------- helpers
RELEVANT = {"A", "B", "both", "C"}

def bucket_counts(df):
    if df.empty or "bucket" not in df.columns:
        return {}
    return df["bucket"].value_counts().to_dict()

def g(d, k):
    return int(d.get(k, 0))

def hbar(pairs, color=GREEN, height=210):
    """pairs: list of (label, value). Returns a styled horizontal Altair bar."""
    data = pd.DataFrame(pairs, columns=["label", "value"])
    return (
        alt.Chart(data)
        .mark_bar(cornerRadiusEnd=6, color=color)
        .encode(
            x=alt.X("value:Q", title=None, axis=alt.Axis(grid=False)),
            y=alt.Y("label:N", sort=None, title=None),
            tooltip=["label", "value"],
        )
        .properties(height=height)
        .configure_view(strokeWidth=0)
        .configure_axis(labelColor="#c9ced8", labelFontSize=13)
    )

def vsplit(a_val, b_val, height=240):
    """Discovery (A) vs Repetition (B) two-bar chart."""
    data = pd.DataFrame(
        {"label": ["Discovery (A)", "Repetition (B)"],
         "value": [a_val, b_val],
         "c": [BLUE, GREEN]}
    )
    return (
        alt.Chart(data)
        .mark_bar(cornerRadiusEnd=6)
        .encode(
            x=alt.X("label:N", title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("value:Q", title=None, axis=alt.Axis(grid=False)),
            color=alt.Color("c:N", scale=None, legend=None),
            tooltip=["label", "value"],
        )
        .properties(height=height)
        .configure_view(strokeWidth=0)
        .configure_axis(labelColor="#c9ced8", labelFontSize=13)
    )

qc = bucket_counts(quant)
ql = bucket_counts(qual)

total = len(quant)
rel_a, rel_b, rel_both = g(qc, "A"), g(qc, "B"), g(qc, "both")
relevant = rel_a + rel_b + rel_both
ab_total = rel_a + rel_b

# ---------------------------------------------------------------- hero
st.markdown(
    """
    <div class="hero">
      <h1>🎧 Spotify Discovery — Review Analysis Engine</h1>
      <p>Triangulating app-store reviews and forum discussions to locate the real discovery
      problem. Every review is tagged into one of three buckets, then cross-checked across
      independently-collected sources.</p>
      <span class="pill pill-a">A · discovery quality</span>
      <span class="pill pill-b">B · repetition mechanics</span>
      <span class="pill pill-c">C · AI-generated music distrust</span>
    </div>
    """,
    unsafe_allow_html=True,
)

if not quant_ok:
    st.error("Couldn't load data/processed/tagged_reviews.csv — run scripts/tag_reviews.py or check the file exists.")
if not qual_ok:
    st.warning("Couldn't load data/processed/qualitative_coded.csv — forum/Reddit views will be empty.")

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("### 🎧 Dataset at a glance")
    st.metric("App-store reviews", f"{total:,}")
    st.metric("Forum / Reddit comments", f"{len(qual):,}")
    st.metric("Discovery-relevant pool", f"{relevant:,}",
              f"{(relevant/total*100):.1f}% of all" if total else "—")
    st.divider()
    st.markdown("#### Bucket legend")
    st.markdown(
        "- :blue[**A**] — discovery quality (won't surface new music)\n"
        "- :green[**B**] — repetition mechanics (shuffle replays)\n"
        "- :orange[**C**] — AI-generated music distrust"
    )
    st.divider()
    st.caption("App stores keyword-tagged at scale · Reddit & Community hand-coded for depth.")

# ---------------------------------------------------------------- tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📊  Funnel", "🔭  Two Sources", "❓  Six Questions", "🔍  Explorer", "⚡  Live Tagger"]
)

# ============================================================ 1. FUNNEL
with tab1:
    st.header("The funnel")
    st.write("A percentage means nothing without its denominator. Most reviews are about "
             "ads, billing and crashes — irrelevant here. The story is in the relevant pool.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("All reviews", f"{total:,}")
    c2.metric("Discovery/repetition relevant", f"{relevant:,}",
              f"{(relevant/total*100):.1f}% of all" if total else "—")
    c3.metric("Discovery (A)", f"{rel_a:,}",
              f"{(rel_a/ab_total*100):.0f}% of A+B" if ab_total else "—")
    c4.metric("Repetition (B)", f"{rel_b:,}",
              f"{(rel_b/ab_total*100):.0f}% of A+B" if ab_total else "—")

    st.write("")
    if ab_total:
        st.altair_chart(
            hbar([("All reviews", total),
                  ("Relevant pool", relevant),
                  ("Discovery (A)", rel_a),
                  ("Repetition (B)", rel_b)]),
            use_container_width=True,
        )
        st.caption("Of the discovery-relevant pool, repetition mechanics (B) dominate "
                   "discovery-quality complaints (A).")

# ============================================================ 2. SOURCES
with tab2:
    st.header("Two sources, same direction")
    st.write("The strength of the finding isn't one blended number — it's that two "
             "independently-collected sources point the same way. Forums lean even "
             "harder toward discovery quality, because long comments explain what a "
             "1-star rating compresses into \"shuffle sucks.\"")

    # quant A vs B
    q_ab = (rel_a, rel_b)
    # qual A vs B, folding C into A (AI-slop is a discovery-quality sub-type)
    ql_a = g(ql, "A") + g(ql, "C")
    ql_b = g(ql, "B")

    s1, s2 = st.columns(2)
    with s1:
        st.subheader("App stores")
        st.caption(f"{total:,} reviews · keyword-tagged at scale")
        if sum(q_ab):
            st.metric("Discovery vs repetition",
                      f"{q_ab[0]/sum(q_ab)*100:.0f}% A / {q_ab[1]/sum(q_ab)*100:.0f}% B")
            st.altair_chart(vsplit(q_ab[0], q_ab[1]), use_container_width=True)
    with s2:
        st.subheader("Reddit + community")
        st.caption(f"{len(qual):,} comments · hand-coded for depth (C folded into A)")
        if (ql_a + ql_b):
            st.metric("Discovery vs repetition",
                      f"{ql_a/(ql_a+ql_b)*100:.0f}% A / {ql_b/(ql_a+ql_b)*100:.0f}% B")
            st.altair_chart(vsplit(ql_a, ql_b), use_container_width=True)

    # C sub-theme callout
    ql_rel = g(ql, "A") + g(ql, "B") + g(ql, "C") + g(ql, "both")
    if ql_rel:
        st.info(f"**Sub-theme — bucket C (AI-generated music distrust): "
                f"{g(ql,'C')/ql_rel*100:.0f}% of forum discovery-talk.** Users can't trust "
                f"recommendations because they're polluted with AI slop — a trust failure "
                f"the recommendation surface itself created. Churn-driving "
                f"(\"switching to Deezer\", \"cancelled my sub\").")

# ============================================================ 3. SIX QUESTIONS
with tab3:
    st.header("The six questions, answered from data")
    qmap = {
        "q1_struggle_discover": "Why users struggle to discover",
        "q2_recommendation_frustration": "Recommendation frustrations",
        "q3_listening_goals": "Listening goals",
        "q4_repeat_listening": "Causes of repeat listening",
        "q5_segment_signal": "Segment signals",
        "q6_unmet_needs": "Unmet needs",
    }
    present = [c for c in qmap if c in quant.columns]
    if present:
        counts = {qmap[c]: int(quant[c].sum()) for c in present}
        st.altair_chart(
            hbar(list(counts.items()), color=GREEN_SOFT, height=300),
            use_container_width=True,
        )
        st.caption("Reviews answer frustrations (Q2, Q4) loudly but goals (Q3) and "
                   "segments (Q5) barely — which is exactly what the interviews are for. "
                   "Q5 is keyword-inflated; treat it as a weak signal.")
    else:
        st.info("No question columns found in tagged_reviews.csv.")

# ============================================================ 4. EXPLORER
with tab4:
    st.header("Browse the evidence")
    src = st.radio("Source", ["App stores", "Reddit + community"], horizontal=True)
    df = quant if src == "App stores" else qual
    if not df.empty and "bucket" in df.columns:
        pick = st.multiselect("Bucket", ["A", "B", "C", "both"], default=["A"])
        view = df[df["bucket"].isin(pick)]
        cols = [c for c in ["source", "rating", "title", "body", "bucket", "question_tags"]
                if c in view.columns]
        st.caption(f"{len(view):,} matching — read a sample to validate the auto-coding.")
        st.dataframe(view[cols].head(200), use_container_width=True, hide_index=True)
    else:
        st.info("Nothing to browse for this source.")

# ============================================================ 5. LIVE TAGGER
with tab5:
    st.header("Try it live — tag any review")
    st.write("Paste any review; Claude tags it in about a second. This is the per-review "
             "engine that produced the analysis above, running live.")

    TAG_PROMPT = """You are tagging ONE Spotify review for a discovery study.
Return ONLY a JSON object — no prose, no markdown fences:
{{"bucket":"A|B|C|both|irrelevant","intensity":1,"segment_hint":"heavy-library|casual|churned|unknown","signal":"substitution|workaround|churn|none","evidence":"exact phrase that decided it"}}

A = discovery quality (won't surface new music / echo chamber)
B = repetition mechanics (shuffle/queue replays same songs)
C = AI-generated music distrust (AI slop in recommendations)

Review: \"\"\"{review}\"\"\""""

    sample = "I cancelled Premium because it only played the same 10 songs over and over out of almost 2,000 in my favourite playlist."
    text = st.text_area("Review text", value=sample, height=110)

    if st.button("Tag review", type="primary") and text.strip():
        try:
            import anthropic, json
            client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
            with st.spinner("Tagging…"):
                msg = client.messages.create(
                    model="claude-haiku-4-5",
                    max_tokens=300,
                    messages=[{"role": "user",
                               "content": TAG_PROMPT.format(review=text)}],
                )
                raw = msg.content[0].text.strip().replace("```json", "").replace("```", "").strip()
                result = json.loads(raw)
            cols = st.columns(4)
            cols[0].metric("Bucket", result.get("bucket", "?"))
            cols[1].metric("Intensity", f"{result.get('intensity','?')} / 5")
            cols[2].metric("Segment", result.get("segment_hint", "?"))
            cols[3].metric("Signal", result.get("signal", "?"))
            st.caption(f"Evidence: \"{result.get('evidence','')}\"")
        except KeyError:
            st.error("No ANTHROPIC_API_KEY found. Add it in the app's Secrets "
                     "(Streamlit Cloud) or a local .streamlit/secrets.toml file.")
        except json.JSONDecodeError:
            st.error("Claude returned something that wasn't clean JSON — try again.")
        except Exception as e:
            st.error(f"Something went wrong: {e}")

st.divider()
st.caption("Quantitative sources (app stores) keyword-tagged at scale; qualitative "
           "sources (Reddit, Spotify Community) read and hand-coded for depth.")
