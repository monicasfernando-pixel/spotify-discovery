# Spotify Discovery — Instructions

## Purpose

This project analyzes **public user feedback** about Spotify's **music discovery experience** — recommendations, shuffle, repetitive listening, and trust in what the algorithm surfaces (including AI-generated music).

It combines:

- **Quantitative data** — ~127k App Store + Google Play reviews, keyword-tagged at scale
- **Qualitative data** — Reddit threads and Spotify Community forum posts, hand-coded for depth
- **Interactive dashboard** — a Streamlit app to explore the funnel, A/B split, six research questions, and a live review tagger (Claude)

The core research finding: users' main discovery pain is **repetition mechanics (B)** — shuffle and curated playlists replay the same songs — not bad taste alone. A secondary trust crisis (**C**) around AI music in recommendations appears strongly in forum data.

---

## Project layout

```
spotify-discovery/
├── app/
│   └── app.py                 # Streamlit dashboard (main application)
├── scripts/
│   ├── tag_reviews.py         # Keyword-tag app-store reviews → tagged_reviews.csv
│   └── scrapers/
│       ├── appstore_scrape.py # Pull Apple App Store reviews (optional refresh)
│       ├── gplay_scrape.py    # Pull Google Play reviews (optional refresh)
│       └── reddit_scrape.py   # Reddit scraper (requires API credentials; optional)
├── data/
│   ├── raw/                   # Scraped review CSVs (inputs)
│   ├── processed/             # Tagged / coded outputs (used by the app)
│   └── sources/               # Original Reddit PDF, Community export, parsed CSV
├── .streamlit/
│   ├── config.toml            # Dark theme
│   └── secrets.toml           # ANTHROPIC_API_KEY (local only — not committed)
├── requirements.txt
├── Instructions.md            # This file
└── WORKFLOW.md                # Pipeline, workflow, and architecture
```

---

## Prerequisites

- **Python 3.10+** (project uses 3.12)
- A virtual environment (recommended)

---

## Setup (first time)

From the project root (`spotify-discovery/`):

```powershell
# 1. Create and activate venv (if you don't have one)
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your Anthropic API key (only needed for the Live Tagger tab)
#    Edit .streamlit/secrets.toml:
#    ANTHROPIC_API_KEY = "your-key-here"
```

Processed data files are already included under `data/processed/`. You do **not** need to re-scrape or re-tag to run the dashboard.

---

## Run the application

From the **project root**:

```powershell
.\venv\Scripts\python.exe -m streamlit run app/app.py
```

Open **http://localhost:8501** in your browser.

### Dashboard tabs

| Tab | What it shows |
|-----|----------------|
| **Funnel** | All reviews → discovery-relevant pool → A vs B split |
| **Two Sources** | App stores vs Reddit/Community — triangulation |
| **Six Questions** | Counts for the six brief research questions |
| **Explorer** | Filter and browse tagged reviews by bucket (A/B/C) |
| **Live Tagger** | Paste any review; Claude tags it in real time (needs API key) |

Tabs 1–4 work without an API key. Tab 5 requires a valid key in `.streamlit/secrets.toml`.

---

## Refresh data (optional)

### Re-tag app-store reviews

After updating files in `data/raw/`:

```powershell
python scripts/tag_reviews.py
```

Writes `data/processed/tagged_reviews.csv`.

**Inputs:** `data/raw/appstore_raw.csv`, `data/raw/gplay_raw.csv`

### Scrape new reviews

```powershell
# Google Play (free, no API key)
python scripts/scrapers/gplay_scrape.py --countries us --count 1000

# App Store (free, per-country RSS feed)
python scripts/scrapers/appstore_scrape.py --countries us gb in --pages 10

# Reddit (requires OAuth app credentials in .env — often blocked for new developers)
python scripts/scrapers/reddit_scrape.py --comments
```

Then run `python scripts/tag_reviews.py` again if you changed raw app-store data.

### Qualitative data

`data/processed/qualitative_coded.csv` is **hand-coded** from Reddit and Spotify Community sources in `data/sources/`. There is no automated script in this repo to regenerate it; update manually if you add new forum threads.

---

## Bucket definitions

| Bucket | Meaning |
|--------|---------|
| **A** | Discovery quality — won't surface new music, echo chamber, bad recommendations |
| **B** | Repetition mechanics — shuffle/queue replays the same songs |
| **C** | AI-generated music distrust — AI slop in Discover Weekly / Release Radar (forum data mainly) |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Couldn't load tagged_reviews.csv` | Run from project root; confirm `data/processed/tagged_reviews.csv` exists |
| Live Tagger: no API key | Set `ANTHROPIC_API_KEY` in `.streamlit/secrets.toml` |
| Port 8501 in use | `streamlit run app/app.py --server.port 8502` |
| Scraper import errors | `pip install google-play-scraper requests` (Play Store scraper extra) |

---

## What was removed

These were duplicates or unused and are no longer in the repo:

- `scrape_appstore.py` — superseded by `scripts/scrapers/appstore_scrape.py`
- `reddit_raw.csv` — empty failed scrape
- `reddit_threads.txt` — duplicate of parsed CSV
- `Data_Redit/` — source docx moved to `data/sources/`
