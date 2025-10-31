#!/usr/bin/env python3
#!/usr/bin/env python3
"""
va_claim_help_scraper1.py
---------------------------------------------------------
Collects posts and comments from veteran-related subreddits.

# INSTALLATION
    python --version         # requires 3.10 or newer
    pip install praw python-dotenv

# SETUP
1. Create a Reddit 'script' app at https://www.reddit.com/prefs/apps
   and copy its client_id and client_secret.
2. Create a file named `.env` in this folder:
       CLIENT_ID=your_client_id
       CLIENT_SECRET=your_client_secret
       USER_AGENT=va_claim_help_scraper1 by u/<your_username> (contact: you@example.com)
       # Optional if using password grant (2FA must be off):
       REDDIT_USERNAME=your_username
       REDDIT_PASSWORD=your_password
3. Place a `keywords.txt` in this folder — one keyword or phrase per line.
   Example:
       service connected
       denied claim
       C&P exam
   You can override with --keywords <path> if it's elsewhere.

# FIRST RUN
    python va_claim_help_scraper1.py --dotenv --doctor
    # Fix any issues it reports.
    python va_claim_help_scraper1.py --dotenv --skip-comments --verbose

# OUTPUT
    - results/<keyword>.json / .csv / .txt
    - summary_log.csv
    - seen_ids.json (for deduping future runs)

# TROUBLESHOOTING
    * Missing praw →  pip install praw
    * OAuthException → check CLIENT_ID/SECRET and app type ('script')
    * FileNotFoundError on keywords → ensure keywords.txt exists or use --keywords
    * PermissionError → choose a writable directory or use --results <path>
    * Rate limit (429) → rerun with higher --sleep or --max-retries

# LICENSE & CREDITS
    This script was written for dissertation research on digital veteran discourse.
    Please use ethically and within Reddit’s Developer Terms.
---------------------------------------------------------
"""
from __future__ import annotations
import argparse
import csv
import json
import logging
import os
import re
import sys
import time
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Dict, Any

# Optional: load .env
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None  # we'll guard later

# Third‑party dependency (must be in requirements.txt)
try:
    import praw # type: ignore
    import prawcore # type: ignore
except Exception as e:
    # Don't crash on import so that --doctor can still print a helpful message
    praw = None  # type: ignore
    prawcore = None  # type: ignore

APP_NAME = "va_claim_help_scraper1"
DEFAULT_RESULTS_DIR = "results"
DEFAULT_SUMMARY_CSV = "summary_log.csv"
DEFAULT_SEEN_IDS_FILE = "seen_ids.json"

# ------------------------- helpers -------------------------

def sanitize_filename(name: str, maxlen: int = 100) -> str:
    """Make a keyword safe as a cross‑platform filename."""
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", name.strip())
    return safe[:maxlen] if safe else "untitled"


def load_json_list(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except Exception:
        # Corrupt file → start fresh rather than crashing
        return []


def save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def append_csv_row(path: Path, header: List[str], row: List[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if not file_exists or path.stat().st_size == 0:
            writer.writerow(header)
        writer.writerow(row)


def now_utc_date(ts: float | int | None) -> str:
    if not ts:
        return "N/A"
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return "N/A"


def periodic_save_seen(seen_ids: set[str], seen_path: Path, counter: int, every: int = 3) -> None:
    """Persist seen IDs every N keywords to guard against crashes."""
    if counter % every == 0:
        try:
            save_json(seen_path, sorted(seen_ids))
        except Exception:
            logging.warning("Could not save seen IDs (periodic). Continuing…")


# ------------------------- preflight doctor -------------------------

def run_doctor(args) -> int:
    """Preflight checks with plain‑English fixes."""
    print("\n=== Preflight: first‑run checks ===")

    # Python version
    py_ok = sys.version_info >= (3, 10)
    print(f"Python version: {sys.version.split()[0]} — {'OK' if py_ok else 'Needs 3.10+'}")

    # dotenv
    if args.dotenv:
        if load_dotenv is None:
            print("python-dotenv not installed. Run: pip install python-dotenv")
        else:
            load_dotenv()
            print("Loaded .env (if present).")

    # PRAW import
    if praw is None:
        print("PRAW not installed. Run: pip install praw")
        return 1

    # Credentials
    cid = os.getenv("CLIENT_ID")
    csec = os.getenv("CLIENT_SECRET")
    uagent = os.getenv("USER_AGENT", f"{APP_NAME} by u/your_username (contact: email)")
    ruser = os.getenv("REDDIT_USERNAME")
    rpass = os.getenv("REDDIT_PASSWORD")

    cred_ok = bool(cid and csec and uagent)
    if not cred_ok:
        print("Missing credentials. Set CLIENT_ID, CLIENT_SECRET, and USER_AGENT in env or .env.")
        print("If using password grant, also set REDDIT_USERNAME and REDDIT_PASSWORD (2FA must be off).")
        return 1
    else:
        print("Found Reddit app credentials.")

    # Keywords file
    kw_path = Path(args.keywords)
    if not kw_path.exists():
        print(f"keywords file not found at: {kw_path}. Create it or pass --keywords <path>.")
        return 1
    else:
        print(f"Found keywords file: {kw_path}")

    # Results dir writable
    results_dir = Path(args.results)
    try:
        results_dir.mkdir(parents=True, exist_ok=True)
        test = results_dir / ".writetest"
        test.write_text("ok", encoding="utf-8")
        test.unlink(missing_ok=True)
        print(f"Results directory writable: {results_dir}")
    except Exception:
        print(f"Cannot write to results directory: {results_dir}. Choose another with --results.")
        return 1

    # Try a lightweight Reddit call
    try:
        reddit = create_reddit(cid, csec, uagent, ruser, rpass)
        _ = reddit.read_only  # touches auth path
        # sanity: fetch subreddit about
        about = reddit.subreddit(args.subreddit).moderator  # a quick property to resolve
        print(f"Reddit API reachable. Subreddit looks accessible: r/{args.subreddit}")
    except prawcore.exceptions.OAuthException:
        print("OAuth error. Ensure your Reddit app is type 'script' and secrets are correct.")
        return 1
    except prawcore.exceptions.Forbidden:
        print(f"Access forbidden to r/{args.subreddit}. Is it private or banned?")
        return 1
    except Exception as e:
        print(f"General API/network error: {e}\nCheck network, proxies, or try again later.")
        return 1

    print("\nAll essential checks passed. You can run the scraper now.")
    return 0


# ------------------------- Reddit client -------------------------

def create_reddit(client_id: str, client_secret: str, user_agent: str, username: str | None, password: str | None):
    if username and password:
        return praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
            username=username,
            password=password,
            ratelimit_seconds=5,
        )
    # Read‑only OAuth
    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
        ratelimit_seconds=5,
    )


# ------------------------- scraping core -------------------------

def search_posts_and_comments(reddit, subreddit_name: str, keywords: List[str],
                              results_dir: Path, summary_csv: Path, seen_ids_path: Path,
                              limit_posts: int, sleep_s: int, max_retries: int,
                              include_comments: bool, verbose: bool) -> None:
    log = logging.getLogger("scraper")

    # Load seen ids
    seen_ids: set[str] = set()
    try:
        if seen_ids_path.exists():
            with seen_ids_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    seen_ids = set(map(str, data))
    except Exception:
        log.warning("seen_ids.json is corrupt; starting fresh.")

    sub = reddit.subreddit(subreddit_name)

    header = [
        "keyword", "posts_found", "comments_found", "oldest_date", "newest_date",
        "outfile_json", "duplicates_skipped"
    ]

    for idx, kw in enumerate(keywords, start=1):
        safe_kw = sanitize_filename(kw)
        json_file = results_dir / f"{safe_kw}.json"
        txt_file = results_dir / f"{safe_kw}.txt"
        csv_file = results_dir / f"{safe_kw}.csv"

        # Load existing JSON bucket for this keyword
        bucket = load_json_list(json_file)
        existing_ids = {item.get("id") for item in bucket if isinstance(item, dict)}

        posts_found = 0
        comments_found = 0
        duplicates = 0
        oldest_ts = None
        newest_ts = None

        def update_dates(ts):
            nonlocal oldest_ts, newest_ts
            if ts is None:
                return
            oldest_ts = ts if oldest_ts is None else min(oldest_ts, ts)
            newest_ts = ts if newest_ts is None else max(newest_ts, ts)

        # --- Search posts for exact phrase (quoted) ---
        q = f'"{kw}"'
        log.info(f"[{idx}/{len(keywords)}] Searching posts for: {q}")

        for attempt in range(1, max_retries + 1):
            try:
                for post in sub.search(q, sort="new", time_filter="all", limit=500):
                    if post.id in seen_ids or post.id in existing_ids:
                        duplicates += 1
                        continue
                    record = {
                        "type": "post",
                        "id": post.id,
                        "subreddit": str(post.subreddit),
                        "title": getattr(post, "title", ""),
                        "body": getattr(post, "selftext", ""),
                        "url": f"https://reddit.com{getattr(post, 'permalink', '')}",
                        "score": getattr(post, "score", 0),
                        "created_utc": getattr(post, "created_utc", None),
                        "matched_keyword": kw,
                    }
                    bucket.append(record)
                    posts_found += 1
                    seen_ids.add(post.id)
                    update_dates(getattr(post, "created_utc", None))
                break  # fetched OK
            except prawcore.exceptions.TooManyRequests as e:
                wait = sleep_s * attempt
                log.warning(f"Rate limited. Sleeping {wait}s (attempt {attempt}/{max_retries})…")
                time.sleep(wait)
            except prawcore.exceptions.ServerError:
                wait = sleep_s * attempt
                log.warning(f"Server error. Sleeping {wait}s (attempt {attempt}/{max_retries})…")
                time.sleep(wait)
            except Exception as e:
                log.error(f"Unexpected error while searching posts: {e}")
                break

        # --- Scan hot posts & comments ---
        if include_comments:
            log.info(f"Scanning hot posts & comments for keyword: {kw}")
            try:
                for post in sub.hot(limit=limit_posts):
                    try:
                        post.comments.replace_more(limit=0)
                        for c in post.comments.list():
                            body = getattr(c, "body", "")
                            if body and kw.lower() in body.lower():
                                cid = getattr(c, "id", None)
                                pid = getattr(post, "id", None)
                                if not cid or (cid in seen_ids):
                                    continue
                                record = {
                                    "type": "comment",
                                    "id": cid,
                                    "post_id": pid,
                                    "subreddit": str(post.subreddit),
                                    "title": getattr(post, "title", ""),
                                    "body": body,
                                    "url": f"https://reddit.com{getattr(c, 'permalink', '')}",
                                    "score": getattr(c, "score", 0),
                                    "created_utc": getattr(c, "created_utc", None),
                                    "matched_keyword": kw,
                                }
                                bucket.append(record)
                                comments_found += 1
                                seen_ids.add(cid)
                                update_dates(getattr(c, "created_utc", None))
                    except Exception as e:
                        log.warning(f"Skipping one hot post due to error: {e}")
            except Exception as e:
                log.warning(f"Hot listing failed: {e}")

        # --- Persist per‑keyword outputs ---
        save_json(json_file, bucket)

        # text file (one JSON line per record for simple grepping)
        with txt_file.open("w", encoding="utf-8") as tf:
            for item in bucket:
                tf.write(json.dumps(item, ensure_ascii=False) + "\n")

        # CSV (flat projection)
        csv_header = [
            "type", "id", "post_id", "subreddit", "title", "body", "url",
            "score", "created_utc", "matched_keyword"
        ]
        with csv_file.open("w", encoding="utf-8", newline="") as cf:
            writer = csv.DictWriter(cf, fieldnames=csv_header)
            writer.writeheader()
            for item in bucket:
                row = {k: item.get(k) for k in csv_header}
                writer.writerow(row)

        # Summary row
        append_csv_row(
            Path(summary_csv),
            header,
            [
                kw,
                posts_found,
                comments_found,
                now_utc_date(oldest_ts),
                now_utc_date(newest_ts),
                str(json_file),
                duplicates,
            ],
        )

        # Periodic save of seen IDs (every 3 keywords)
        periodic_save_seen(seen_ids, Path(seen_ids_path), idx, every=3)

        # Throttle between keywords
        if sleep_s > 0:
            time.sleep(sleep_s)

    # Final save of seen IDs
    try:
        save_json(Path(seen_ids_path), sorted(seen_ids))
    except Exception:
        log.warning("Could not save final seen IDs.")


# ------------------------- entrypoint -------------------------

def main():
    parser = argparse.ArgumentParser(description="VA claims helper: Reddit scraper with doctor & guards.")
    parser.add_argument("--dotenv", action="store_true", help="Load a .env file from the project root if present.")
    parser.add_argument("--doctor", action="store_true", help="Run preflight checks and exit.")
    parser.add_argument("--keywords", default="keywords.txt", help="Path to keywords.txt (one per line).")
    parser.add_argument("--subreddit", default="VeteransBenefits", help="Target subreddit.")
    parser.add_argument("--results", default=DEFAULT_RESULTS_DIR, help="Directory to write results.")
    parser.add_argument("--summary-csv", default=DEFAULT_SUMMARY_CSV, help="Path to summary CSV.")
    parser.add_argument("--seen-ids", default=DEFAULT_SEEN_IDS_FILE, help="Path to seen IDs JSON.")

    parser.add_argument("--limit-posts", type=int, default=200, help="Hot posts to scan for comments.")
    parser.add_argument("--sleep", type=int, default=3, help="Seconds to sleep between keywords and on backoff.")
    parser.add_argument("--max-retries", type=int, default=3, help="Retries for rate‑limit/server errors.")
    parser.add_argument("--skip-comments", action="store_true", help="Do not scan comments (faster).")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging.")

    parser.add_argument("--no-summary", action="store_true", help="Skip generating the summary report script.")
    parser.add_argument("--no-pdf", action="store_true", help="Skip generating the PDF report script.")
    parser.add_argument("--no-sync", action="store_true", help="Skip syncing to Google Sheets.")

    args = parser.parse_args()

    if args.dotenv and load_dotenv is not None:
        load_dotenv()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    if args.doctor:
        rc = run_doctor(args)
        sys.exit(rc)

    # Validate essentials (friendly exits)
    if praw is None:
        raise SystemExit("PRAW is not installed. Run: pip install praw")

    kw_path = Path(args.keywords)
    if not kw_path.exists():
        raise SystemExit(
            f"keywords file not found at {kw_path}. Put keywords.txt next to the script or pass --keywords <path>."
        )

    try:
        with kw_path.open("r", encoding="utf-8") as f:
            keywords = [line.strip() for line in f if line.strip()]
    except Exception as e:
        raise SystemExit(f"Could not read keywords file: {e}")

    # Secrets
    cid = os.getenv("CLIENT_ID")
    csec = os.getenv("CLIENT_SECRET")
    uagent = os.getenv("USER_AGENT", f"{APP_NAME} by u/your_username (contact: email)")
    ruser = os.getenv("REDDIT_USERNAME")
    rpass = os.getenv("REDDIT_PASSWORD")

    if not (cid and csec):
        raise SystemExit(
            "Missing CLIENT_ID/CLIENT_SECRET. Set them in your environment or a .env file (use --dotenv)."
        )

    reddit = create_reddit(cid, csec, uagent, ruser, rpass)

    # Run scraper
    search_posts_and_comments(
        reddit=reddit,
        subreddit_name=args.subreddit,
        keywords=keywords,
        results_dir=Path(args.results),
        summary_csv=Path(args.summary_csv),
        seen_ids_path=Path(args.seen_ids),
        limit_posts=args.limit_posts,
        sleep_s=args.sleep,
        max_retries=args.max_retries,
        include_comments=not args.skip_comments,
        verbose=args.verbose,
    )

    # Post‑run helpers (portable subprocess)
    here = Path(__file__).resolve().parent
    py = sys.executable or "python3"

    if not args.no_summary:
        summ = here / "generate_summary_report.py"
        if summ.exists():
            try:
                subprocess.run([py, str(summ)], check=True)
            except Exception as e:
                print(f"Note: summary generator failed: {e}. You can rerun it later.")
        else:
            print("Note: generate_summary_report.py not found; skipping summary step.")

    if not args.no_pdf:
        pdf = here / "generate_pdf_report.py"
        if pdf.exists():
            try:
                subprocess.run([py, str(pdf)], check=True)
            except Exception as e:
                print(f"Note: PDF generator failed: {e}. You can rerun it later.")
        else:
            print("Note: generate_pdf_report.py not found; skipping PDF step.")

    if not args.no_sync:
        sync = here / "sync_to_google_sheet.py"
        if sync.exists():
            try:
                subprocess.run([py, str(sync)], check=True)
            except Exception as e:
                print(
                    "Note: Google Sheets sync failed. First run may require OAuth in a browser. "
                    f"Error: {e}"
                )
        else:
            print("Note: sync_to_google_sheet.py not found; skipping Sheets sync.")

    print("\nDone. Outputs are in:", Path(args.results).resolve())
    print("Summary CSV:", Path(args.summary_csv).resolve())


if __name__ == "__main__":
    main()
