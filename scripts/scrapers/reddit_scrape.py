"""Scrape Spotify discussion from Reddit into reddit_raw.csv.

Schema mirrors appstore_raw.csv so the datasets are comparable:
    source, country, review_id, author, rating, title, body, version, updated

- Works with NO credentials via Reddit's public JSON API (rate-limited).
- If REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET are set (in venv/.env or env),
  it uses the authenticated OAuth API, which is faster and more reliable.

Usage:
    python reddit_scrape.py
    python reddit_scrape.py --subreddits spotify truespotify --limit 200 --comments
"""

import argparse
import csv
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent.parent

DEFAULT_SUBREDDITS = ["spotify", "truespotify"]

# Theme-focused queries (discovery + the other themes from the App Store analysis)
DEFAULT_QUERIES = [
    "recommendations",
    "discover weekly",
    "algorithm",
    "repetitive",
    "shuffle same songs",
    "radio suggestions",
    "ads",
    "price increase expensive",
    "crash bug glitch",
    "account login problem",
]

ENV_PATH = ROOT / ".env"
OUT_PATH = ROOT / "data" / "raw" / "reddit_raw.csv"
FIELDS = ["source", "country", "review_id", "author", "rating",
          "title", "body", "version", "updated"]


def load_env(path):
    """Minimal .env parser (no python-dotenv dependency)."""
    env = {}
    if not os.path.exists(path):
        return env
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            env[key.strip()] = val.strip()
    return env


def iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def get_oauth_session(env):
    """Return (session, base_url) using OAuth if real creds exist, else public."""
    cid = env.get("REDDIT_CLIENT_ID", "")
    secret = env.get("REDDIT_CLIENT_SECRET", "")
    ua = env.get("REDDIT_USER_AGENT", "spotify-discovery-script")

    placeholder = (not cid or not secret or cid == "..." or secret == "...")
    sess = requests.Session()
    sess.headers["User-Agent"] = ua

    if placeholder:
        print("[info] No Reddit credentials -> using public JSON API (rate-limited).")
        return sess, "https://www.reddit.com", False

    try:
        auth = requests.auth.HTTPBasicAuth(cid, secret)
        resp = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=auth,
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": ua},
            timeout=30,
        )
        resp.raise_for_status()
        token = resp.json()["access_token"]
        sess.headers["Authorization"] = f"bearer {token}"
        print("[info] Authenticated with Reddit OAuth API.")
        return sess, "https://oauth.reddit.com", True
    except Exception as e:
        print(f"[warn] OAuth failed ({e}); falling back to public JSON API.")
        return sess, "https://www.reddit.com", False


def fetch_json(sess, url, params, retries=4):
    for attempt in range(retries):
        resp = sess.get(url, params=params, timeout=30)
        if resp.status_code == 429:
            wait = 2 ** attempt
            print(f"[warn] 429 rate-limited; sleeping {wait}s")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()


def search_subreddit(sess, base, sub, query, limit):
    """Yield post 'data' dicts for a subreddit search, paginating."""
    fetched = 0
    after = None
    while fetched < limit:
        params = {
            "q": query,
            "restrict_sr": 1,
            "sort": "relevance",
            "t": "all",
            "limit": min(100, limit - fetched),
            "raw_json": 1,
        }
        if after:
            params["after"] = after
        data = fetch_json(sess, f"{base}/r/{sub}/search.json", params)
        children = data.get("data", {}).get("children", [])
        if not children:
            break
        for c in children:
            yield c["data"]
            fetched += 1
        after = data.get("data", {}).get("after")
        if not after:
            break
        time.sleep(1.0)  # be polite


def fetch_top_comments(sess, base, sub, post_id, max_comments=5):
    params = {"limit": max_comments, "sort": "top", "raw_json": 1}
    try:
        data = fetch_json(sess, f"{base}/r/{sub}/comments/{post_id}.json", params)
    except Exception:
        return []
    out = []
    if len(data) > 1:
        for c in data[1].get("data", {}).get("children", []):
            d = c.get("data", {})
            if d.get("body") and d.get("body") not in ("[deleted]", "[removed]"):
                out.append(d)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subreddits", nargs="+", default=DEFAULT_SUBREDDITS)
    ap.add_argument("--queries", nargs="+", default=DEFAULT_QUERIES)
    ap.add_argument("--limit", type=int, default=100,
                    help="max posts per (subreddit, query)")
    ap.add_argument("--comments", action="store_true",
                    help="also scrape top comments of each post")
    ap.add_argument("--out", default=OUT_PATH)
    args = ap.parse_args()

    env = {**load_env(str(ENV_PATH)), **os.environ}
    sess, base, _ = get_oauth_session(env)

    seen = set()
    rows = []
    for sub in args.subreddits:
        for query in args.queries:
            print(f"[scrape] r/{sub} q='{query}'")
            try:
                posts = list(search_subreddit(sess, base, sub, query, args.limit))
            except Exception as e:
                print(f"[warn] search failed r/{sub} '{query}': {e}")
                continue
            for p in posts:
                pid = p.get("id")
                if not pid or pid in seen:
                    continue
                seen.add(pid)
                rows.append({
                    "source": "reddit",
                    "country": "na",
                    "review_id": p.get("id"),
                    "author": p.get("author"),
                    "rating": p.get("score"),
                    "title": p.get("title", ""),
                    "body": p.get("selftext", ""),
                    "version": f"r/{sub}",
                    "updated": iso(p.get("created_utc", 0)),
                })
                if args.comments:
                    for cm in fetch_top_comments(sess, base, sub, pid):
                        cid = cm.get("id")
                        if not cid or cid in seen:
                            continue
                        seen.add(cid)
                        rows.append({
                            "source": "reddit_comment",
                            "country": "na",
                            "review_id": cm.get("id"),
                            "author": cm.get("author"),
                            "rating": cm.get("score"),
                            "title": p.get("title", ""),
                            "body": cm.get("body", ""),
                            "version": f"r/{sub}",
                            "updated": iso(cm.get("created_utc", 0)),
                        })
                    time.sleep(0.5)
            time.sleep(1.0)

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    print(f"\n[done] wrote {len(rows)} rows -> {args.out}")


if __name__ == "__main__":
    main()
