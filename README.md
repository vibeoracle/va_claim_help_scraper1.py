# Reddit VeteransBenefits Subreddit Scraper and Report Generator (Public Version)

This repository contains a Python script that scrapes posts and comments from the **r/VeteransBenefits** subreddit using keyword-based searches. It supports deduplication, exports data in multiple formats (JSON, CSV, TXT), and logs run statistics for transparency and reproducibility. After scraping, the script can optionally trigger report generation and data syncing.

---

## Key Features

* Scrapes posts containing keywords from `keywords.txt`
* Collects comments from top (hot) posts that include those keywords
* Deduplicates data across runs using `seen_ids.json`
* Saves results in JSON, CSV, and TXT formats inside the `results/` folder
* Logs per-run statistics (post count, comment count, oldest/newest dates, duplicates skipped) to `summary_log.csv`
* Optionally runs:
  * `generate_summary_report.py` – creates data summaries and visualizations
  * `generate_pdf_report.py` – exports findings to PDF
  * `sync_to_google_sheet.py` – syncs summary data to Google Sheets (if enabled)
* Designed for **incremental, reproducible, and ethical data collection**

---

## 📁 Project Structure

```bash
VeteransBenefits_VA_Claim_Help/
├── keywords.txt                  # List of search terms (one per line)
├── summary_log.csv               # Run statistics
├── seen_ids.json                 # Deduplication record
├── results/                      # Output .json, .csv, .txt files
├── va_claim_help_scraper.py      # Main scraping script
├── generate_summary_report.py    # Optional analytics
├── generate_pdf_report.py        # Optional PDF export
├── sync_to_google_sheet.py       # Optional Google Sheets sync
├── requirements.txt
├── .env.example                  # Sample environment variable file
└── .gitignore
```

---

## ⚙️ Setup Instructions

1. **Clone or download this repository**
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Set up Reddit API credentials:**
   * Create a Reddit app (type: *script*) at [https://www.reddit.com/prefs/apps](https://www.reddit.com/prefs/apps)
   * Copy the provided `.env.example` file to `.env` and fill in your credentials:
     ```bash
     REDDIT_CLIENT_ID=your_id_here
     REDDIT_CLIENT_SECRET=your_secret_here
     REDDIT_USERNAME=your_username
     REDDIT_PASSWORD=your_password
     REDDIT_USER_AGENT=va-claims-scraper/1.0 by u/your_username
     ```
4. **Prepare keywords:**
   * Add search terms to `keywords.txt` (one per line)
5. **Run the scraper:**
   ```bash
   python3 va_claim_help_scraper.py
   ```
6. (Optional) **Enable Google Sheets sync:**
   * Add to your `.env` file:
     ```bash
     SHEETS_ENABLED=true
     SHEETS_ID=your_google_sheet_id
     SHEETS_RANGE=Sheet1!A1
     ```

---

## 🚀 Preflight / First-Run Checklist

Before your first full scrape, run these quick checks to avoid common setup issues:

1. **Python version** — Confirm you’re running **3.10 or newer**  
   ```bash
   python --version
   ```

2. **Dependencies installed** — Make sure required packages are available  
   ```bash
   pip install -r requirements.txt
   ```

3. **Reddit app configured** — Verify your Reddit app is type **“script”** under [https://www.reddit.com/prefs/apps](https://www.reddit.com/prefs/apps)

4. **.env file created** — Ensure your `.env` file in the project folder contains:
   ```bash
   CLIENT_ID=your_client_id
   CLIENT_SECRET=your_client_secret
   USER_AGENT=va_claim_help_scraper1 by u/<your_username> (contact: you@example.com)
   # Optional if using password grant (2FA must be off):
   REDDIT_USERNAME=your_username
   REDDIT_PASSWORD=your_password
   ```

5. **Keywords file ready** — Confirm `keywords.txt` exists and lists one keyword or phrase per line.  
   Example:
   ```
   service connected
   denied claim
   C&P exam
   ```

6. **Run the built-in preflight tool** — This checks your Python version, dependencies, credentials, and permissions:  
   ```bash
   python va_claim_help_scraper1.py --dotenv --doctor
   ```
   Fix any issues it reports before continuing.

7. **Test run (quick mode)** — Run a shorter test that skips comments:  
   ```bash
   python va_claim_help_scraper1.py --dotenv --skip-comments --verbose
   ```
   When everything looks good, remove `--skip-comments` for full runs.

8. **Optional helper steps** — If present, omit the `--no-summary`, `--no-pdf`, and `--no-sync` flags to automatically:  
   * Generate summary and PDF reports  
   * Sync summary data to Google Sheets (OAuth may open a browser on first run)

---

## Throttling & Error Handling

* The script uses small pauses (`time.sleep()`) between requests to comply with Reddit’s rate limits.
* Deduplication ensures no post or comment is logged twice.
* Errors (e.g., missing comments, failed API calls) are caught and logged but do not stop execution.

---

## Dependencies

The script relies on the following libraries:

* `praw` – Reddit API wrapper (BSD-2-Clause)
* `prawcore` – Reddit API utilities (BSD-2-Clause)
* `pandas` – Data manipulation (BSD-3-Clause)
* `matplotlib` – Visualizations (PSF)
* `fpdf` – PDF generation (LGPL)
* `gspread` + `oauth2client` – Google Sheets integration (Apache 2.0)

All dependencies can be installed from `requirements.txt`.

---

## License & Use

Released under the **MIT License**. 

This project interacts with Reddit’s API via PRAW. Users are responsible for following [Reddit’s API Terms of Use](https://www.redditinc.com/policies/data-api-terms), including restrictions on rate limits, data storage, and redistribution. No scraped data is included in this repository.

---

## .gitignore

```gitignore
# Bytecode and cache
__pycache__/
*.py[cod]

# Environments
venv/
.env

# Credentials and tokens
*.json

# Outputs and logs
results/
summary_log*.csv
seen_ids.json
scraper.log

# OS-specific files
.DS_Store
```

---

## Acknowledgment

This open version was collaboratively refined with assistance from **ChatGPT‑5**, focusing on reproducibility, privacy, and readability for researchers exploring digital discourse.
