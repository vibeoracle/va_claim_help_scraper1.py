README
# Reddit VeteransBenefits Subreddit Scraper and Report Generator

This Python script scrapes posts and comments from the r/VeteransBenefits subreddit using keyword-based searches. It includes deduplication, multi-format export (JSON, CSV, TXT), and logging features to support research workflows. After scraping, the script can automatically trigger summary report generation, PDF report creation, and optional syncing to Google Sheets.

---

## Features

* Scrapes posts containing keywords from `keywords.txt`
* Collects comments from popular (hot) posts that contain the same keywords
* Deduplicates content across runs using `seen_ids.json`
* Exports results to JSON, CSV, and TXT formats in the `results/` folder
* Logs run statistics (post count, comment count, oldest/newest dates, duplicates skipped) to `summary_log.csv`
* Automatically runs:

  * `generate_summary_report.py` for data summaries and visualizations
  * `generate_pdf_report.py` for PDF output
  * `sync_to_google_sheet.py` for syncing summary data to Google Sheets
* Designed for repeatable, incremental data collection

---

## Project Structure

```bash
VeteransBenefits_VA_Claim_Help/
├── keywords.txt
├── summary_log.csv
├── seen_ids.json
├── results/               # Output .json, .csv, .txt files
├── va_claim_help_scraper.py
├── generate_summary_report.py
├── generate_pdf_report.py
├── sync_to_google_sheet.py
├── requirements.txt
└── .gitignore
```

---

## Setup Instructions

1. **Clone or download the repository**
2. **Install required dependencies:**

   ```bash
   pip install -r requirements.txt
   ```
3. **Set up Reddit API access:**

   * Create a Reddit App (type: script) at [https://www.reddit.com/prefs/apps](https://www.reddit.com/prefs/apps)
   * Save your `client_id`, `client_secret`, `username`, and `password` in environment variables (recommended) or in the script
4. **Prepare keywords file:**

   * Place search terms in `keywords.txt`, one per line
5. **Run the script:**

   ```bash
   python3 va_claim_help_scraper.py
   ```

---

## Throttling and Error Handling

The script uses `time.sleep()` to space out requests and avoid hitting Reddit’s API rate limits. Deduplication is handled by tracking processed IDs in `seen_ids.json`. Errors in fetching comments or running reports are caught and logged without halting the entire run.

---

## Dependencies

This project uses the following Python libraries:

* `praw` – Reddit API access (BSD-2-Clause license)
* `prawcore` – Reddit API utilities (BSD-2-Clause license)
* `pandas` – data handling and summary tables (BSD-3-Clause license)
* `matplotlib` – visualizations (PSF license)
* `fpdf` – PDF generation (LGPL)
* `gspread` + `oauth2client` – Google Sheets syncing (Apache 2.0 license)

Install them via `requirements.txt`.

---

## License and Use

This project is released under the **MIT License**.

Dependencies keep their original licenses (listed above).

This script uses the Reddit API through PRAW. Anyone running it is responsible for following [Reddit’s API Terms of Use](https://www.redditinc.com/policies/data-api-terms), including rate limits and restrictions on storing or redistributing content. This repository includes only the code, not large scraped datasets.

---

## .gitignore

```gitignore
# Python bytecode
__pycache__/
*.py[cod]

# Virtual environments
venv/
.env

# API keys or service files
*.json

# Output and logs
scraper.log
results/
summary_log*.csv
seen_ids.json

# OS-specific
.DS_Store
```

---

## Acknowledgment

This README was drafted with the assistance of ChatGPT-5 to help with clarity and formatting.
