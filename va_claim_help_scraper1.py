import praw
import json
import csv
from datetime import datetime, timezone
import os
import time
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# ================================
# Reddit VA Claim Help Scraper (Public/Anonymized Version)
# ================================
# This version removes all personal identifiers and allows anyone to plug in their
# own Reddit API credentials, keywords file, and optional integrations.
#
# It scrapes r/VeteransBenefits for posts and comments containing specified keywords,
# storing results in JSON, CSV, and TXT formats while preventing duplicates.

# --- Load Environment Variables ---
load_dotenv()

# --- Reddit API Setup ---
# Create a Reddit API app at https://www.reddit.com/prefs/apps
# and add your credentials to a .env file (see README for example).
REDDIT = praw.Reddit(
    client_id=os.getenv("REDDIT_CLIENT_ID", "YOUR_CLIENT_ID"),
    client_secret=os.getenv("REDDIT_CLIENT_SECRET", "YOUR_CLIENT_SECRET"),
    user_agent=os.getenv("REDDIT_USER_AGENT", "va-claims-scraper/1.0 by u/your_username"),
    username=os.getenv("REDDIT_USERNAME", "YOUR_USERNAME"),
    password=os.getenv("REDDIT_PASSWORD", "YOUR_PASSWORD"),
)

# --- Config ---
subreddit = REDDIT.subreddit("VeteransBenefits")
limit_posts = 200
summary_csv = "summary_log.csv"
seen_ids_file = "seen_ids.json"

# --- Load or Initialize Seen IDs ---
if os.path.exists(seen_ids_file):
    with open(seen_ids_file, "r", encoding="utf-8") as f:
        seen_ids = set(json.load(f))
else:
    seen_ids = set()

# --- Load keywords ---
# Users can specify a file path with KEYWORDS_FILE in their .env, otherwise it defaults to keywords.txt.
keywords_path = os.getenv("KEYWORDS_FILE", "keywords.txt")
with open(keywords_path, "r", encoding="utf-8") as f:
    keywords = [line.strip() for line in f if line.strip()]

keywords.sort(key=len, reverse=True)

# --- Create CSV Summary Log ---
if not os.path.exists(summary_csv):
    with open(summary_csv, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            "keyword", "post_count", "comment_count", "oldest_date", "newest_date", "json_filename", "skipped_duplicates"
        ])

# --- Main Loop ---
for search_phrase in keywords:
    print("\n" + "=" * 60)
    print(f"🔎 Searching: \"{search_phrase}\"")
    results = []
    post_count = 0
    comment_count = 0
    skipped = 0

    # --- Search posts ---
    for post in subreddit.search(f'"{search_phrase}"', sort="new", time_filter="all", limit=500):
        if post.id in seen_ids:
            skipped += 1
            continue
        seen_ids.add(post.id)
        post_count += 1
        results.append({
            "type": "post",
            "id": post.id,
            "title": post.title,
            "body": post.selftext,
            "url": f"https://www.reddit.com{post.permalink}",
            "score": post.score,
            "created_utc": post.created_utc,
            "matched_keyword": search_phrase
        })

    # --- Search comments ---
    for post in subreddit.hot(limit=limit_posts):
        try:
            post.comments.replace_more(limit=0)
            for comment in post.comments.list():
                if search_phrase in comment.body.lower():
                    if comment.id in seen_ids:
                        skipped += 1
                        continue
                    seen_ids.add(comment.id)
                    comment_count += 1
                    results.append({
                        "type": "comment",
                        "id": comment.id,
                        "post_title": post.title,
                        "comment_body": comment.body,
                        "url": f"https://www.reddit.com{comment.permalink}",
                        "score": comment.score,
                        "created_utc": comment.created_utc,
                        "matched_keyword": search_phrase
                    })
        except Exception as e:
            print(f" Skipping comments on post due to error: {e}")

    # --- Save results ---
    os.makedirs("results", exist_ok=True)
    json_file = os.path.join("results", f"{search_phrase.replace(' ', '_')}.json")
    txt_file = os.path.join("results", f"{search_phrase.replace(' ', '_')}.txt")
    csv_file = os.path.join("results", f"{search_phrase.replace(' ', '_')}.csv")

    existing_json = []
    if os.path.exists(json_file):
        with open(json_file, "r", encoding="utf-8") as jf:
            try:
                existing_json = json.load(jf)
            except json.JSONDecodeError:
                existing_json = []

    with open(json_file, "w", encoding="utf-8") as jf:
        json.dump(existing_json + results, jf, indent=2, ensure_ascii=False)

    with open(txt_file, "a", encoding="utf-8") as tf:
        for entry in results:
            if entry["type"] == "post":
                tf.write("=== POST ===\n")
                tf.write(f"Title: {entry['title']}\n")
                tf.write(f"Body: {entry['body']}\n")
            elif entry["type"] == "comment":
                tf.write("=== COMMENT ===\n")
                tf.write(f"Post Title: {entry['post_title']}\n")
                tf.write(f"Comment: {entry['comment_body']}\n")
            tf.write(f"URL: {entry['url']}\n")
            tf.write(f"Score: {entry['score']}\n")
            tf.write(f"Date: {datetime.fromtimestamp(entry['created_utc'], timezone.utc).strftime('%Y-%m-%d')}\n")
            tf.write("-" * 80 + "\n")

    with open(csv_file, "a", newline="", encoding="utf-8") as cf:
        fieldnames = [
            "type", "id", "title", "body", "post_title", "comment_body", "url", "score", "created_utc", "matched_keyword"
        ]
        writer = csv.DictWriter(cf, fieldnames=fieldnames)
        if not os.path.exists(csv_file) or os.stat(csv_file).st_size == 0:
            writer.writeheader()
        for row in results:
            full_row = {field: row.get(field, "") for field in fieldnames}
            writer.writerow(full_row)

    if results:
        timestamps = [r["created_utc"] for r in results]
        oldest_date = datetime.fromtimestamp(min(timestamps), timezone.utc).strftime("%Y-%m-%d")
        newest_date = datetime.fromtimestamp(max(timestamps), timezone.utc).strftime("%Y-%m-%d")
    else:
        oldest_date = "N/A"
        newest_date = "N/A"

    with open(summary_csv, "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            search_phrase,
            post_count,
            comment_count,
            oldest_date,
            newest_date,
            os.path.basename(json_file),
            skipped
        ])

    print(f" {post_count} posts, {comment_count} comments")
    print(f" Range: {oldest_date} to {newest_date}")
    print(f" Skipped {skipped} duplicate matches")
    print(f" Appended to:\n- {json_file}\n- {txt_file}\n- {csv_file}")
    time.sleep(3)

# --- Save Seen IDs ---
with open(seen_ids_file, "w", encoding="utf-8") as f:
    json.dump(list(seen_ids), f, indent=2)

# --- Optional: Auto-run Summary or PDF Scripts ---
try:
    print("\n🚰 Generating summary report and graphs...")
    subprocess.run(["python3", "generate_summary_report.py"], check=True)
except Exception as e:
    print(f" Failed to generate summary report automatically: {e}")

try:
    subprocess.run(["python3", "generate_pdf_report.py"], check=True)
except Exception as e:
    print(f" Failed to generate PDF report: {e}")

# --- Optional: Sync to Google Sheets (if enabled) ---
if os.getenv("SHEETS_ENABLED", "false").lower() == "true":
    try:
        subprocess.run(["python3", "sync_to_google_sheet.py"], check=True)
    except Exception as e:
        print(f" Failed to sync to Google Sheets: {e}")
