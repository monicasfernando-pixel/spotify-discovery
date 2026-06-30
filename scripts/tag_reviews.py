"""
tag_reviews.py
---------------
Classifies your scraped reviews against the six brief questions, plus a coarse
A/B bucket (A = discovery quality, B = repetition mechanics).

No API key, no cost — pure keyword matching. Reproducible and fast.

Run from project root (venv active):
    python scripts/tag_reviews.py

Inputs : data/raw/appstore_raw.csv, data/raw/gplay_raw.csv
Output : data/processed/tagged_reviews.csv  +  printed per-question counts
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

# ---------------- CONFIG ----------------
INPUT_FILES = [RAW / "appstore_raw.csv", RAW / "gplay_raw.csv"]
OUTPUT_FILE = PROCESSED / "tagged_reviews.csv"
# ----------------------------------------

# Each brief question maps to a list of lowercased phrases.
QUESTION_KEYWORDS = {
    "q1_struggle_discover": [
        "discover", "discovery", "find new", "new music", "new artist",
        "new song", "nothing new", "can't find", "cant find", "hard to find",
    ],
    "q2_recommendation_frustration": [
        "recommend", "recommendation", "suggest", "algorithm", "discover weekly",
        "daily mix", " dj ", "radio", "bad picks", "same artist", "made for you",
    ],
    "q3_listening_goals": [
        "mood", "focus", "workout", "background", "variety", "explore",
        "branch out", "expand", "fresh", "study", "sleep",
    ],
    "q4_repeat_listening": [
        "same song", "same music", "over and over", "repeat", "repetitive",
        "loop", "shuffle", "rotation", "only play", "liked song", "same stuff",
    ],
    "q5_segment_signal": [
        "premium", "family", "student", "cancel", "switched", "casual",
        "thousand", "huge playlist", "for years", "longtime", "long time",
    ],
    "q6_unmet_needs": [
        "wish", "please add", "need", "should be able", "why can't", "why cant",
        "feature request", "dislike button", "block", "exclude", "blacklist",
    ],
}

# Coarse A/B bucket keyword sets
BUCKET_A = QUESTION_KEYWORDS["q1_struggle_discover"] + \
           QUESTION_KEYWORDS["q2_recommendation_frustration"] + \
           ["echo chamber", "stale", "lane", "trust", "boring", "predictable"]
BUCKET_B = QUESTION_KEYWORDS["q4_repeat_listening"]


def matches(text, keywords):
    return any(k in text for k in keywords)


def main():
    frames = []
    for f in INPUT_FILES:
        try:
            df = pd.read_csv(f)
            frames.append(df)
            print(f"Loaded {len(df):,} rows from {f.name}")
        except FileNotFoundError:
            print(f"  (skipped — {f.name} not found)")

    if not frames:
        print("No input files found. Check the file names in INPUT_FILES.")
        return

    df = pd.concat(frames, ignore_index=True)
    df.drop_duplicates(subset=["review_id"], inplace=True)

    # One combined text field, lowercased, for matching
    text = (df["title"].fillna("") + " " + df["body"].fillna("")).str.lower()

    # Tag each question
    for q, kws in QUESTION_KEYWORDS.items():
        df[q] = text.apply(lambda t: matches(t, kws))

    # Coarse A/B bucket
    a = text.apply(lambda t: matches(t, BUCKET_A))
    b = text.apply(lambda t: matches(t, BUCKET_B))
    df["bucket"] = "irrelevant"
    df.loc[a & ~b, "bucket"] = "A"
    df.loc[b & ~a, "bucket"] = "B"
    df.loc[a & b, "bucket"] = "both"

    # Human-readable list of which questions each review hit
    qcols = list(QUESTION_KEYWORDS.keys())
    df["question_tags"] = df[qcols].apply(
        lambda row: ",".join([q for q in qcols if row[q]]), axis=1
    )

    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8")

    total = len(df)
    print(f"\nSaved {total:,} tagged reviews to {OUTPUT_FILE}\n")
    print("Per-question hits (a review can hit several):")
    for q in qcols:
        n = int(df[q].sum())
        print(f"  {q:32s} {n:>7,}  ({n/total*100:4.1f}%)")

    print("\nA/B bucket split:")
    for b_name in ["A", "B", "both", "irrelevant"]:
        n = int((df["bucket"] == b_name).sum())
        print(f"  {b_name:10s} {n:>7,}  ({n/total*100:4.1f}%)")


if __name__ == "__main__":
    main()
