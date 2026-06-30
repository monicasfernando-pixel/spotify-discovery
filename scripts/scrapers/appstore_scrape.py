"""Scrape Spotify reviews from the Apple App Store, per country.

Free, no API key (uses Apple's public customer-reviews RSS-JSON feed).
Unlike Google Play, the App Store feed IS country-specific, so reviews from
US / GB / IN are genuinely distinct -> you can bifurcate insights by country.

Schema mirrors appstore_raw.csv:
    source, country, review_id, author, rating, title, body, version, updated

Note: Apple's feed caps at ~500 most-recent reviews PER storefront and has
no date filter. To get more volume / a 6-month window, scrape many storefronts
(--all) and post-filter by date (--months).

Usage:
    python appstore_scrape.py
    python appstore_scrape.py --countries us gb in --pages 10
    python appstore_scrape.py --all --months 6 --out appstore_multi.csv
"""

import argparse
import csv
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUT = ROOT / "data" / "raw" / "appstore_multi.csv"

APP_ID = "324684580"  # Spotify on the App Store
DEFAULT_COUNTRIES = ["us", "gb", "in"]

# Broad set of App Store storefronts (high-volume + global spread).
ALL_COUNTRIES = [
    "us", "gb", "ca", "au", "ie", "nz", "za", "in", "ph", "sg", "my", "ng",
    "pk", "ae", "sa", "eg", "id", "th", "vn", "hk", "tw", "jp", "kr",
    "de", "fr", "es", "it", "nl", "be", "pt", "se", "no", "dk", "fi", "pl",
    "at", "ch", "cz", "gr", "ro", "hu", "ua", "tr", "ru",
    "br", "mx", "ar", "cl", "co", "pe", "ec",
]
FIELDS = ["source", "country", "review_id", "author", "rating",
          "title", "body", "version", "updated"]
UA = "Mozilla/5.0 (compatible; spotify-discovery-research/1.0)"


def fetch_page(sess, url, retries=4):
    """Fetch one feed page with backoff. Returns entries list (may be empty)."""
    for attempt in range(retries):
        try:
            resp = sess.get(url, timeout=30)
            if resp.status_code in (403, 429, 503):
                wait = 2 ** attempt
                print(f"          [throttle {resp.status_code}] wait {wait}s")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json().get("feed", {}).get("entry", []), True
        except Exception as e:
            wait = 2 ** attempt
            print(f"          [warn] {e}; retry in {wait}s")
            time.sleep(wait)
    return [], False


def scrape_country(app_id, country, pages, sess):
    """Apple's feed exposes up to ~10 pages (~50 reviews each)."""
    out = []
    for page in range(1, pages + 1):
        url = (f"https://itunes.apple.com/{country}/rss/customerreviews/"
               f"page={page}/id={app_id}/sortby=mostrecent/json")
        entries, ok = fetch_page(sess, url)
        # First entry is app metadata, not a review (only on page 1).
        if entries and "im:rating" not in entries[0]:
            entries = entries[1:]
        if not entries:
            # Page 1 empty after retries = likely throttled/no data; stop.
            break
        out.extend(entries)
        time.sleep(0.8)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default=APP_ID)
    ap.add_argument("--countries", nargs="+", default=DEFAULT_COUNTRIES)
    ap.add_argument("--all", action="store_true",
                    help="scrape the broad ALL_COUNTRIES storefront list")
    ap.add_argument("--pages", type=int, default=10,
                    help="pages per country (Apple caps around 10)")
    ap.add_argument("--months", type=int, default=None,
                    help="keep only reviews from the last N months")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    countries = ALL_COUNTRIES if args.all else args.countries
    cutoff = None
    if args.months:
        cutoff = datetime.now(timezone.utc) - timedelta(days=30 * args.months)

    sess = requests.Session()
    sess.headers["User-Agent"] = UA

    seen = set()
    rows = []
    dropped_old = 0
    for country in countries:
        print(f"[scrape] App Store id={args.app} country={country}")
        entries = scrape_country(args.app, country, args.pages, sess)
        added = 0
        for e in entries:
            rid = e.get("id", {}).get("label")
            if not rid or rid in seen:
                continue
            updated = e.get("updated", {}).get("label", "")
            if cutoff is not None and updated:
                try:
                    dt = datetime.fromisoformat(updated)
                    if dt < cutoff:
                        dropped_old += 1
                        continue
                except ValueError:
                    pass
            seen.add(rid)
            rows.append({
                "source": "app_store",
                "country": country,
                "review_id": rid,
                "author": e.get("author", {}).get("name", {}).get("label", ""),
                "rating": e.get("im:rating", {}).get("label", ""),
                "title": e.get("title", {}).get("label", ""),
                "body": (e.get("content", {}).get("label", "") or "").replace("\r", " "),
                "version": e.get("im:version", {}).get("label", ""),
                "updated": updated,
            })
            added += 1
        print(f"          kept {added} reviews")
        time.sleep(1.5)
    if cutoff is not None:
        print(f"[info] dropped {dropped_old} reviews older than {cutoff.date()}")

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    print(f"\n[done] wrote {len(rows)} rows -> {args.out}")


if __name__ == "__main__":
    main()
