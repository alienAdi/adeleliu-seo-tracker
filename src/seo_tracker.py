#!/usr/bin/env python3
"""Collect monthly Google results, preserve history, report changes, and sync Sheets."""

from __future__ import annotations

import csv
import json
import os
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "config" / "keywords.json"
HISTORY_FILE = ROOT / "data" / "rankings_history.csv"
REPORTS_DIR = ROOT / "reports"
FIELDNAMES = ["date", "keyword", "rank", "url", "title", "snippet"]


def load_config() -> dict[str, Any]:
    with CONFIG_FILE.open(encoding="utf-8") as config_file:
        return json.load(config_file)


def get_organic_results(keyword: str, serp: dict[str, str]) -> list[dict[str, str]]:
    api_key = os.environ.get("SERPAPI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing SERPAPI_API_KEY GitHub secret.")

    response = requests.get(
        "https://serpapi.com/search.json",
        params={
            "engine": "google",
            "q": keyword,
            "location": serp["location"],
            "google_domain": serp["google_domain"],
            "hl": serp["language"],
            "gl": serp["country"],
            "num": 20,
            "api_key": api_key,
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise RuntimeError(f"SERP API error for {keyword}: {payload['error']}")

    results: list[dict[str, str]] = []
    for item in payload.get("organic_results", [])[:20]:
        rank = item.get("position")
        url = item.get("link")
        if rank and url:
            results.append(
                {
                    "rank": str(rank),
                    "url": url,
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                }
            )
    return results


def read_history() -> list[dict[str, str]]:
    if not HISTORY_FILE.exists():
        return []
    with HISTORY_FILE.open(encoding="utf-8", newline="") as history_file:
        return list(csv.DictReader(history_file))


def write_history(rows: list[dict[str, str]]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("w", encoding="utf-8", newline="") as history_file:
        writer = csv.DictWriter(history_file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def last_snapshot(rows: list[dict[str, str]], current_date: str) -> dict[tuple[str, str], int]:
    dates = sorted({row["date"] for row in rows if row["date"] < current_date})
    if not dates:
        return {}
    previous_date = dates[-1]
    return {
        (row["keyword"], row["url"]): int(row["rank"])
        for row in rows
        if row["date"] == previous_date
    }


def md_list(items: list[str], empty: str) -> str:
    return "\n".join(f"- {item}" for item in items) if items else f"- {empty}"


def build_reports(
    current_rows: list[dict[str, str]], previous: dict[tuple[str, str], int], month: str
) -> tuple[str, str]:
    rises: list[str] = []
    declines: list[str] = []
    new_pages: list[str] = []
    best_rank: dict[str, int] = defaultdict(lambda: 99)

    for row in current_rows:
        keyword, url, rank = row["keyword"], row["url"], int(row["rank"])
        best_rank[keyword] = min(best_rank[keyword], rank)
        old_rank = previous.get((keyword, url))
        label = f"{keyword}: #{rank} — {row['title'] or url}"
        if old_rank is None:
            new_pages.append(label)
        elif rank < old_rank:
            rises.append(f"{label} (#{old_rank} → #{rank})")
        elif rank > old_rank:
            declines.append(f"{label} (#{old_rank} → #{rank})")

    weak = [keyword for keyword, rank in best_rank.items() if rank > 10]
    if not previous:
        month_context = "這是第一個基準月；下次執行後才會顯示升降幅度。"
    else:
        month_context = "排名比較基於上一個已儲存的月度快照。"

    report = f"""# SEO 月報 — {month}

{month_context}

## 排名上升

{md_list(rises, '本月沒有可比較的上升項目。')}

## 排名下降

{md_list(declines, '本月沒有可比較的下降項目。')}

## 新出現頁面

{md_list(new_pages, '本月沒有新出現頁面。')}

## 需加強關鍵字

{md_list([f'{keyword}（最佳排名 #{best_rank[keyword]}）' for keyword in weak], '所有關鍵字至少有一個結果進入前 10 名。')}

## 下個月內容建議

{md_list([
    f'以「{keyword}」製作一篇具體、可搜尋的繁中內容，並加入相關食譜、地點或行程的內部連結。'
    for keyword in (weak[:5] or list(best_rank)[:3])
], '持續更新現有表現最佳的內容，補足圖片說明、標題與內部連結。')}
"""

    action_items = [
        "IG：為本月需加強的關鍵字製作 2 支 Reels；在字幕與貼文首段自然寫入完整關鍵字。",
        "Facebook：分享 1 篇長貼文，連回最相關的食譜、旅遊或生活文章。",
        "YouTube：製作 1 支可搜尋的料理／拿坡里生活影片，影片標題與說明加入目標關鍵字。",
        "網站：更新 2 篇相關文章的 H1、meta description、圖片 alt 文字與內部連結。",
    ]
    if declines:
        action_items.append("網站：優先檢查排名下降頁面的內容新鮮度、失效連結與搜尋意圖是否仍吻合。")
    checklist = f"""# SEO 行動清單 — {month}

## 本月優先關鍵字

{md_list(weak[:5], '維護目前排名前 10 的關鍵字內容。')}

## 行動

{md_list(action_items, '')}
"""
    return report, checklist


def sync_google_sheets(rows: list[dict[str, str]], report: str, month: str) -> None:
    sheet_id = os.environ.get("GOOGLE_SHEETS_ID")
    service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not sheet_id and not service_account_json:
        print("Google Sheets sync skipped: secrets are not configured.")
        return
    if not sheet_id or not service_account_json:
        raise RuntimeError("Both GOOGLE_SHEETS_ID and GOOGLE_SERVICE_ACCOUNT_JSON are required.")

    import gspread
    from google.oauth2.service_account import Credentials

    credentials = Credentials.from_service_account_info(
        json.loads(service_account_json),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    spreadsheet = gspread.authorize(credentials).open_by_key(sheet_id)
    try:
        rankings = spreadsheet.worksheet("Rankings")
    except gspread.WorksheetNotFound:
        rankings = spreadsheet.add_worksheet(title="Rankings", rows=1000, cols=6)
    rankings.clear()
    rankings.update([FIELDNAMES] + [[row[field] for field in FIELDNAMES] for row in rows], "A1")

    try:
        reports = spreadsheet.worksheet("Reports")
    except gspread.WorksheetNotFound:
        reports = spreadsheet.add_worksheet(title="Reports", rows=100, cols=2)
    reports.append_row([month, report])
    print("Google Sheets sync completed.")


def main() -> None:
    config = load_config()
    timestamp = datetime.now(UTC)
    current_date = timestamp.date().isoformat()
    month = timestamp.strftime("%Y-%m")
    history = read_history()
    current_rows: list[dict[str, str]] = []

    for keyword in config["keywords"]:
        print(f"Collecting: {keyword}")
        for result in get_organic_results(keyword, config["serp"]):
            current_rows.append({"date": current_date, "keyword": keyword, **result})

    previous = last_snapshot(history, current_date)
    combined_history = history + current_rows
    write_history(combined_history)

    report, checklist = build_reports(current_rows, previous, month)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / f"{month}-seo-report.md").write_text(report, encoding="utf-8")
    (REPORTS_DIR / f"{month}-action-checklist.md").write_text(checklist, encoding="utf-8")
    sync_google_sheets(combined_history, report, month)
    print(f"Saved {len(current_rows)} ranking rows for {current_date}.")


if __name__ == "__main__":
    main()
