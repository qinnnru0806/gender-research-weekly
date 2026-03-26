#!/usr/bin/env python3
"""
fetch_sources.py
抓取所有 RSS 來源的最新文章，輸出為 JSON 供後續摘要使用

修復重點：
1. 使用 requests + User-Agent 避免被期刊網站擋 (403)
2. 加入 retry 機制與完整錯誤處理
3. 日期過濾失敗時自動放寬到 30 天，避免永遠抓不到文章
4. 每個來源獨立 try-except，一個失敗不影響其他
"""

import feedparser
import yaml
import json
import os
import re
import sys
import time
import hashlib
import requests as req_lib
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 強制設定 stdout/stderr 為 UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# 偽裝成瀏覽器，避免被學術出版商 (SAGE, Taylor & Francis, Duke) 擋掉
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 20


def load_config(config_path: str = "sources.yaml") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def parse_pub_date(entry) -> datetime | None:
    """嘗試從 feed entry 取得發布時間，失敗回傳 None"""
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    # 嘗試手動 parse 常見格式
    for attr in ("published", "updated"):
        raw = getattr(entry, attr, None)
        if raw:
            for fmt in (
                "%a, %d %b %Y %H:%M:%S %z",
                "%a, %d %b %Y %H:%M:%S %Z",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d",
            ):
                try:
                    dt = datetime.strptime(raw.strip(), fmt)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except ValueError:
                    continue
    return None


def entry_id(entry) -> str:
    """產生唯一 ID"""
    key = getattr(entry, "id", None) or getattr(entry, "link", "") or entry.get("title", "")
    return hashlib.md5(key.encode()).hexdigest()


def fetch_rss_with_requests(url: str) -> str | None:
    """
    用 requests（帶 User-Agent）下載 RSS XML，
    再交給 feedparser 解析。避免 feedparser 內建 urllib 被擋。
    """
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    for attempt in range(3):
        try:
            resp = req_lib.get(url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code in (403, 429):
                wait = 5 * (attempt + 1)
                print(f"      [WARN] HTTP {resp.status_code}，等 {wait}s 後重試 ({attempt+1}/3)")
                time.sleep(wait)
            else:
                print(f"      [WARN] HTTP {resp.status_code}")
                return None
        except req_lib.exceptions.Timeout:
            print(f"      [WARN] 逾時，重試 ({attempt+1}/3)")
            time.sleep(3)
        except req_lib.exceptions.ConnectionError as e:
            print(f"      [WARN] 連線失敗: {type(e).__name__}")
            return None
        except Exception as e:
            print(f"      [WARN] 錯誤: {e}")
            return None
    return None


def fetch_journals(config: dict, days_back: int) -> tuple[list[dict], list[dict]]:
    """
    抓取所有學術期刊 RSS。
    回傳 (strict_results, loose_results)：
    - strict: days_back 天內的文章
    - loose: 30 天內的文章（fallback 用）
    """
    cutoff_strict = datetime.now(timezone.utc) - timedelta(days=days_back)
    cutoff_loose = datetime.now(timezone.utc) - timedelta(days=30)
    strict_results = []
    loose_results = []
    stats = {"success": 0, "fail": 0, "empty": 0}

    journals = config.get("journals", [])
    print(f"  共 {len(journals)} 個來源")
    print(f"  嚴格 cutoff = {cutoff_strict.strftime('%Y-%m-%d')}")
    print(f"  寬鬆 cutoff = {cutoff_loose.strftime('%Y-%m-%d')}\n")

    for source in journals:
        name = source["name"]
        url = source.get("url", "")
        category = source["category"]
        color = source.get("color", "📄")

        if not url:
            print(f"  ⏭️  {color} {name} — 無 URL，跳過")
            continue

        print(f"  📡 {color} {name}")

        xml_text = fetch_rss_with_requests(url)
        if not xml_text:
            print(f"      ❌ 無法取得 RSS feed")
            stats["fail"] += 1
            continue

        feed = feedparser.parse(xml_text)

        if feed.bozo and not feed.entries:
            print(f"      ❌ 解析失敗: {feed.bozo_exception}")
            stats["fail"] += 1
            continue

        n_strict = 0
        n_loose = 0

        for entry in feed.entries:
            pub_date = parse_pub_date(entry)
            title = entry.get("title", "（無標題）").strip()
            link = entry.get("link", "")
            abstract = (
                entry.get("summary", "")
                or entry.get("description", "")
                or ""
            ).strip()
            abstract = re.sub(r"<[^>]+>", "", abstract).strip()[:1500]

            item = {
                "id": entry_id(entry),
                "source_name": name,
                "source_category": category,
                "source_color": color,
                "title": title,
                "link": link,
                "abstract": abstract,
                "pub_date": (pub_date or datetime.now(timezone.utc)).isoformat(),
                "type": "journal",
            }

            if pub_date and pub_date >= cutoff_strict:
                strict_results.append(item)
                n_strict += 1
            if pub_date is None or pub_date >= cutoff_loose:
                loose_results.append(item)
                n_loose += 1

        if n_strict > 0:
            print(f"      ✅ {n_strict} 篇（{days_back} 天內）")
            stats["success"] += 1
        elif n_loose > 0:
            print(f"      ⚠️  {days_back}天內無，但30天內有 {n_loose} 篇")
            stats["success"] += 1
        else:
            print(f"      ⚠️  共 {len(feed.entries)} 筆但都太舊")
            stats["empty"] += 1

        time.sleep(1)

    print(f"\n  📊 成功 {stats['success']} / 失敗 {stats['fail']} / 無新文章 {stats['empty']}")
    return strict_results, loose_results


def load_seen_ids(seen_path: str) -> set:
    if os.path.exists(seen_path):
        try:
            with open(seen_path, "r") as f:
                return set(json.load(f))
        except (json.JSONDecodeError, TypeError):
            return set()
    return set()


def save_seen_ids(seen_path: str, seen_ids: set):
    with open(seen_path, "w") as f:
        json.dump(list(seen_ids), f)


def main():
    print("=" * 50)
    print("[START] 抓取性別研究 RSS 來源")
    print("=" * 50 + "\n")

    config = load_config("sources.yaml")
    days_back = config.get("days_lookback", 7)
    max_items = config.get("max_items_per_run", 8)

    seen_path = "data/seen_ids.json"
    Path("data").mkdir(exist_ok=True)
    seen_ids = load_seen_ids(seen_path)
    print(f"  已知 {len(seen_ids)} 個推播過的 ID\n")

    strict, loose = fetch_journals(config, days_back)

    # 決定用哪組結果
    if strict:
        all_items = strict
        print(f"\n✅ 嚴格篩選 ({days_back} 天)：{len(strict)} 篇")
    elif loose:
        all_items = loose
        print(f"\n⚠️  嚴格篩選無結果，改用寬鬆 (30 天)：{len(loose)} 篇")
    else:
        all_items = []
        print("\n❌ 所有來源都沒有抓到文章")

    if not all_items:
        with open("data/fetched_articles.json", "w", encoding="utf-8") as f:
            json.dump([], f)
        print("   輸出空 JSON，後續步驟會跳過摘要生成")
        return

    # 過濾已推播
    new_items = [item for item in all_items if item["id"] not in seen_ids]
    print(f"  去重後剩 {len(new_items)} 篇新文章")

    if not new_items:
        print("  全部都推播過了，取最新的重新推播")
        new_items = all_items

    new_items.sort(key=lambda x: x["pub_date"], reverse=True)
    selected = new_items[:max_items]

    output_path = "data/fetched_articles.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(selected, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已選出 {len(selected)} 篇 → {output_path}")
    for item in selected:
        print(f"   • [{item['source_category']}] {item['title'][:60]}")

    for item in selected:
        seen_ids.add(item["id"])
    save_seen_ids(seen_path, seen_ids)


if __name__ == "__main__":
    main()
