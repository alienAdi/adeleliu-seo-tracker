# Adele Liu SEO tracker

GitHub Actions runs this project at **00:00 UTC on the first day of every month** (and can be started manually from the Actions tab). It collects the first 20 Google results for ten selected keywords, preserves the CSV history, creates a Markdown report and action checklist, and optionally mirrors the history to Google Sheets.

## What it produces

- `data/rankings_history.csv` — date, keyword, rank, URL, title, and snippet for each organic result.
- `reports/YYYY-MM-seo-report.md` — ranking gains, losses, newly appearing pages, weak keywords, and content suggestions.
- `reports/YYYY-MM-action-checklist.md` — actions for Instagram, Facebook, YouTube, and the website.

## Required GitHub secret

Create a [SerpApi](https://serpapi.com/) account, then in **Settings → Secrets and variables → Actions** add:

| Secret | Value |
| --- | --- |
| `SERPAPI_API_KEY` | Your SerpApi private API key. |

The workflow stops without this secret, so it never silently records incomplete ranking data.

## Optional Google Sheets sync

To enable the Sheets mirror, add both secrets below:

| Secret | Value |
| --- | --- |
| `GOOGLE_SHEETS_ID` | The ID between `/d/` and `/edit` in the Google Sheets URL. |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | The complete JSON content of a Google service-account key, as a single secret value. |

Share the target spreadsheet with the service account's `client_email` as an editor. The workflow will create `Rankings` and `Reports` sheets if needed. If neither Sheets secret is set, tracking and reports still complete and the workflow explicitly skips the sync.

## Change keywords or locale

Edit `config/keywords.json`. The default Google search locale is Italy (`google.it`) with Traditional Chinese search language, suitable for the Italian / Chinese content in this project.

## First run

After adding `SERPAPI_API_KEY`, open **Actions → Monthly SEO tracker → Run workflow**. The first run establishes a baseline; later runs compare results with the latest earlier snapshot.

## Privacy

Keep API keys and service-account JSON only in GitHub Secrets. They are intentionally not committed to this repository.
