#!/usr/bin/env python3
"""
fetch_sources.py
抓取所有 RSS 來源的最新文章，輸出為 JSON 供後續摘要使用
"""

import feedparser
import yaml
import json
import os
import sys
import time
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 強制設定 stdout/stderr 為 UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def load_config(config_path: str = "sources.yaml") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def parse_pub_date(entry) -> datetime:
    """嘗試從 feed entry 取得發布時間，失敗則回傳現在時間"""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def entry_id(entry) -> str:
    """產生唯一 ID（避免重複推播）"""
    key = getattr(entry, "id", None) or getattr(entry, "link", "") or entry.get("title", "")
    return hashlib.md5(key.encode()).hexdigest()


def fetch_journals(config: dict, days_back: int) -> list[dict]:
    """抓取所有學術期刊 RSS"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    results = []

    for source in config.get("journals", []):
        name = source["name"]
        url = source["url"]
        category = source["category"]
        color = source.get("color", "📄")

        print(f"  抓取 {color} {name} ...")
        try:
            feed = feedparser.parse(url)
            entries_found = 0

            for entry in feed.entries:
                pub_date = parse_pub_date(entry)

                # 只取設定天數內的文章
                if pub_date < cutoff:
                    continue

                title = entry.get("title", "（無標題）").strip()
                link = entry.get("link", "")
                abstract = (
                    entry.get("summary", "")
                    or entry.get("description", "")
                    or ""
                ).strip()

                # 清理 HTML tag（簡易版）
                import re
                abstract = re.sub(r"<[^>]+>", "", abstract).strip()
                abstract = abstract[:1500]  # 最多傳 1500 字給 Claude

                results.append({
                    "id": entry_id(entry),
                    "source_name": name,
                    "source_category": category,
                    "source_color": color,
                    "title": title,
                    "link": link,
                    "abstract": abstract,
                    "pub_date": pub_date.isoformat(),
                    "type": "journal",
                })
                entries_found += 1

            print(f"    [OK] 找到 {entries_found} 篇新文章")
            time.sleep(1)  # 禮貌性 delay，避免被擋

        except Exception as e:
            print(f"    [FAIL] 抓取失敗：{e}")

    return results


def load_seen_ids(seen_path: str) -> set:
    """載入已推播過的文章 ID，避免重複"""
    if os.path.exists(seen_path):
        with open(seen_path, "r") as f:
            return set(json.load(f))
    return set()


def save_seen_ids(seen_path: str, seen_ids: set):
    with open(seen_path, "w") as f:
        json.dump(list(seen_ids), f)


def main():
    print("[START] 開始抓取性別研究 RSS 來源...\n")

    config = load_config("sources.yaml")
    days_back = config.get("days_lookback", 7)
    max_items = config.get("max_items_per_run", 8)

    # 載入已推播 ID（去重用）
    seen_path = "data/seen_ids.json"
    Path("data").mkdir(exist_ok=True)
    seen_ids = load_seen_ids(seen_path)

    # 抓取資料
    all_items = fetch_journals(config, days_back)

    # 過濾已推播
    new_items = [item for item in all_items if item["id"] not in seen_ids]
    print(f"\n[INFO] 本週共抓到 {len(all_items)} 篇，其中 {len(new_items)} 篇是新的")

    # 按日期排序，取最新 max_items 篇
    new_items.sort(key=lambda x: x["pub_date"], reverse=True)
    selected = new_items[:max_items]

    # 輸出 JSON 供 summarize.py 使用
    output_path = "data/fetched_articles.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(selected, f, ensure_ascii=False, indent=2)

    print(f"\n[OK] 已選出 {len(selected)} 篇，儲存至 {output_path}")

    # 更新 seen_ids（加入本次選出的，避免下週重複）
    for item in selected:
        seen_ids.add(item["id"])
    save_seen_ids(seen_path, seen_ids)


if __name__ == "__main__":
    main()
