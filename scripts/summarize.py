#!/usr/bin/env python3
"""
summarize.py
呼叫 Claude API，為每篇文章生成中文摘要（含台灣脈絡分析與小編評語）
"""

import anthropic
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

# 強制設定 stdout/stderr 為 UTF-8，避免特殊字元造成編碼錯誤
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


SYSTEM_PROMPT = """你是「新世紀直男戰士」Podcast 的研究助理，專精性別研究與台灣性別議題脈絡。

你的任務是為一篇學術文章撰寫中文摘要，讓台灣的一般聽眾能輕鬆讀懂，同時保留足夠的學術深度。

摘要風格要求：
- 語氣像在跟朋友解釋，不要學術腔，但不能流於膚淺
- 用繁體中文台灣用語（不用「里程碑」「獲取」「賦能」等中國用語）
- 小編評語要有個性，可以批評方法論、指出有趣的矛盾、或說為什麼這個研究很重要
- 台灣脈絡分析要誠實：如果台灣情況不同要說明，不要硬套

請嚴格按照以下 JSON 格式回答，不要加任何其他文字：

{
  "title_zh": "文章中文標題（自行翻譯）",
  "category_tag": "分類標籤（如：男性求助行為、跨性別照顧、情緒勞動等）",
  "tldr": "一句話說完這篇在幹嘛（20字以內，有點犀利）",
  "whats_this": "這篇研究在做什麼？用2-3句話說清楚，不用提研究方法",
  "key_findings": [
    "主要發現 1（盡量附數字/比例）",
    "主要發現 2",
    "主要發現 3（最多3點）"
  ],
  "taiwan_context": "這個研究跟台灣有什麼關聯？或為什麼在台灣的情況可能不同？（2-3句）",
  "editor_note": "小編有話說：這裡可以有一點個人觀點，像是指出研究的有趣矛盾、挑戰常見論述、或說為什麼這篇值得關注。語氣要吸引人繼續讀原文。（3-5句）",
  "podcast_potential": 1
}

podcast_potential 評分標準（1-5）：
5 = 非常適合做成節目企劃，台灣觀眾會很有感
4 = 可以作為某集的重要素材
3 = 值得參考，但需要跟其他研究搭配
2 = 學術上有趣但較難轉化為節目
1 = 台灣脈絡關聯性較低"""


def sanitize(text: str) -> str:
    """將特殊 Unicode 字元替換為 ASCII 相近字元"""
    if not text:
        return text
    replacements = {
        '\u2014': '--',   # em dash
        '\u2013': '-',    # en dash
        '\u2018': "'",    # left single quote
        '\u2019': "'",    # right single quote
        '\u201c': '"',    # left double quote
        '\u201d': '"',    # right double quote
        '\u2026': '...',  # ellipsis
        '\u00e9': 'e',    # é
        '\u00e8': 'e',    # è
        '\u00ea': 'e',    # ê
        '\u00e0': 'a',    # à
        '\u00e2': 'a',    # â
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text


def summarize_article(client: anthropic.Anthropic, article: dict) -> dict | None:
    """呼叫 Claude API 生成單篇摘要"""

    user_message = f"""請為以下學術文章撰寫中文摘要：

**來源期刊：** {sanitize(article['source_name'])}（{sanitize(article['source_category'])}）
**文章標題：** {sanitize(article['title'])}
**發布日期：** {article['pub_date'][:10]}
**原始連結：** {article['link']}

**摘要/內文片段：**
{sanitize(article['abstract']) or '（此來源未提供摘要，請根據標題進行分析）'}"""

    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1200,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}]
        )

        raw = response.content[0].text.strip()

        # 清理可能的 markdown code block
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        summary = json.loads(raw)
        summary["original_title"] = article["title"]
        summary["link"] = article["link"]
        summary["source_name"] = article["source_name"]
        summary["source_category"] = article["source_category"]
        summary["source_color"] = article.get("source_color", "📄")
        summary["pub_date"] = article["pub_date"][:10]
        summary["id"] = article["id"]

        return summary

    except json.JSONDecodeError as e:
        print(f"    [WARN] JSON 解析失敗：{e}")
        print(f"    原始回應：{raw[:200]}")
        return None
    except Exception as e:
        print(f"    [FAIL] API 呼叫失敗：{e}")
        return None


def main():
    print("[START] 開始生成 AI 摘要...\n")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("請設定 ANTHROPIC_API_KEY 環境變數")

    client = anthropic.Anthropic(api_key=api_key)

    # 讀取抓取到的文章
    input_path = "data/fetched_articles.json"
    if not os.path.exists(input_path):
        print("[FAIL] 找不到 fetched_articles.json，請先執行 fetch_sources.py")
        return

    with open(input_path, "r", encoding="utf-8") as f:
        articles = json.load(f)

    if not articles:
        print("[SKIP] 本週沒有新文章，跳過摘要生成")
        # 建立空的摘要檔
        with open("data/summaries.json", "w", encoding="utf-8") as f:
            json.dump([], f)
        return

    summaries = []
    for i, article in enumerate(articles, 1):
        safe_title = article['title'][:50].encode('ascii', errors='replace').decode('ascii')
        print(f"  [{i}/{len(articles)}] {safe_title}...")
        summary = summarize_article(client, article)
        if summary:
            summaries.append(summary)
            print(f"    [OK] done (podcast_potential: {summary.get('podcast_potential', 1)})")
        else:
            print(f"    [SKIP]")

        # 避免 rate limit
        if i < len(articles):
            time.sleep(2)

    # 按節目潛力排序
    summaries.sort(key=lambda x: x.get("podcast_potential", 1), reverse=True)

    # 儲存摘要
    output_path = "data/summaries.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2)

    print(f"\n[OK] 共生成 {len(summaries)} 篇摘要，儲存至 {output_path}")

    # 顯示本週精選預覽
    print("\n[INFO] 本週精選預覽：")
    for s in summaries[:5]:
        print(f"  [{s.get('podcast_potential',1)}*] {s['title_zh']}")
        print(f"     → {s['tldr']}")


if __name__ == "__main__":
    main()
