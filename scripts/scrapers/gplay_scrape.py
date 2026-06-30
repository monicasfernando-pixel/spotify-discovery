"""Scrape Spotify reviews from the Google Play Store into gplay_raw.csv.

Free, no API key required (uses the public google-play-scraper library).

Schema mirrors appstore_raw.csv so the datasets are comparable:
    source, country, review_id, author, rating, title, body, version, updated

Note: Google Play reviews have no title field, so `title` is left blank.

Usage:
    python gplay_scrape.py
    python gplay_scrape.py --countries us gb in --count 1000
    python gplay_scrape.py --months 6          # last 6 months
    python gplay_scrape.py --since 2026-01-01   # everything since a date
"""

import argparse
import csv
import time
from datetime import datetime, timedelta
from pathlib import Path

from google_play_scraper import Sort, reviews

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUT = ROOT / "data" / "raw" / "gplay_raw.csv"

APP_ID = "com.spotify.music"
DEFAULT_COUNTRIES = ["us"]
FIELDS = ["source", "country", "review_id", "author", "rating",
          "title", "body", "version", "updated"]


def scrape_country(app_id, country, lang, want, sort, cutoff=None,
                   batch=200, hard_cap=200000):
    """Page through reviews for one country.

    Stops when:
      - `cutoff` is set and we reach reviews older than it (date mode), OR
      - we have collected `want` reviews (count mode), OR
      - Google Play runs out of pages / we hit the hard safety cap.
    """
    collected = []
    token = None
    while True:
        if cutoff is None and len(collected) >= want:
            break
        if len(collected) >= hard_cap:
            print(f"          [stop] hit hard cap of {hard_cap}")
            break
        n = batch if cutoff is not None else min(batch, want - len(collected))

        # Retry empty pages: Google Play often throttles with an empty
        # response after many rapid requests (e.g. switching countries).
        result = []
        for attempt in range(4):
            result, token = reviews(
                app_id, lang=lang, country=country, sort=sort,
                count=n, continuation_token=token,
            )
            if result:
                break
            wait = 2 ** attempt
            print(f"          [retry] empty page, waiting {wait}s", flush=True)
            time.sleep(wait)
        if not result:
            break
        collected.extend(result)

        if cutoff is not None:
            oldest = result[-1].get("at")
            if oldest and oldest < cutoff:
                break  # paged past the cutoff date
            if collected:
                newest_dt = collected[0].get("at")
                oldest_dt = result[-1].get("at")
                print(f"          ... {len(collected)} so far "
                      f"(reached {oldest_dt})", flush=True)

        if token is None:
            break
        time.sleep(0.5)  # be polite
    return collected


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default=APP_ID, help="Google Play package name")
    ap.add_argument("--countries", nargs="+", default=DEFAULT_COUNTRIES)
    ap.add_argument("--lang", default="en")
    ap.add_argument("--count", type=int, default=1000,
                    help="max reviews per country (ignored if --months/--since set)")
    ap.add_argument("--months", type=int, default=None,
                    help="scrape reviews from the last N months")
    ap.add_argument("--since", default=None,
                    help="scrape reviews on/after this date (YYYY-MM-DD)")
    ap.add_argument("--sort", choices=["newest", "rating", "relevance"],
                    default="newest")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    sort_map = {
        "newest": Sort.NEWEST,
        "rating": Sort.RATING,
        "relevance": Sort.MOST_RELEVANT,
    }
    sort = sort_map[args.sort]

    cutoff = None
    if args.since:
        cutoff = datetime.fromisoformat(args.since)
    elif args.months:
        cutoff = datetime.now() - timedelta(days=30 * args.months)
    if cutoff is not None and args.sort != "newest":
        print("[info] date cutoff requires newest sort; switching to newest.")
        sort = Sort.NEWEST

    seen = set()
    rows = []
    for country in args.countries:
        if cutoff is not None:
            print(f"[scrape] {args.app} country={country} "
                  f"(since {cutoff.date()})")
        else:
            print(f"[scrape] {args.app} country={country} (up to {args.count})")
        try:
            result = scrape_country(args.app, country, args.lang,
                                    args.count, sort, cutoff=cutoff)
        except Exception as e:
            print(f"[warn] failed for {country}: {e}")
            continue
        added = 0
        for r in result:
            rid = r.get("reviewId")
            if not rid or rid in seen:
                continue
            at = r.get("at")
            if cutoff is not None and at and at < cutoff:
                continue  # trim the tail that overshot the cutoff
            seen.add(rid)
            rows.append({
                "source": "play_store",
                "country": country,
                "review_id": rid,
                "author": r.get("userName"),
                "rating": r.get("score"),
                "title": "",  # Google Play reviews have no title
                "body": (r.get("content") or "").replace("\r", " "),
                "version": r.get("reviewCreatedVersion") or "",
                "updated": at.isoformat() if at else "",
            })
            added += 1
        print(f"          got {added} unique reviews")
        time.sleep(3.0)  # pause between countries to avoid throttling

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    print(f"\n[done] wrote {len(rows)} rows -> {args.out}")


if __name__ == "__main__":
    main()
