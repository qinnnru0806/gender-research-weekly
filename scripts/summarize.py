#!/usr/bin/env python3
"""
summarize.py
呼叫 Claude API，為每篇文章生成中文摘要（含台灣脈絡分析與小編評語）
"""

import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

# 強制 UTF-8（在 import anthropic 之前）
# 注意：PYTHONIOENCODING 只在啟動時生效，所以也要在 shell 層設定
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import anthropic  # noqa: E402


def safe_print(msg: str):
    """絕對不會因為 encoding 而 crash 的 print"""
    try:
        print(msg)
    except UnicodeEncodeError:
        # 最後防線：全部轉 ASCII
        print(msg.encode("ascii", errors="replace").decode("ascii"))


def safe_str(obj) -> str:
    """安全地把任何物件轉成可 print 的字串"""
    try:
        s = str(obj)
        # 測試是否能被 stdout 編碼
        s.encode(sys.stdout.encoding or "ascii")
        return s
    except (UnicodeEncodeError, UnicodeDecodeError, LookupError):
        try:
            return repr(obj)
        except Exception:
            return "(cannot display error)"


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

MODEL = "claude-sonnet-4-6"


def sanitize(text: str) -> str:
    if not text:
        return text
    replacements = {
        '\u2014': '--', '\u2013': '-',
        '\u2018': "'", '\u2019': "'",
        '\u201c': '"', '\u201d': '"',
        '\u2026': '...',
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text


def extract_json(raw: str) -> dict | None:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        text = text[start:end]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def summarize_article(client: anthropic.Anthropic, article: dict, retry: int = 2) -> dict | None:
    user_message = f"""請為以下學術文章撰寫中文摘要：

**來源期刊：** {sanitize(article['source_name'])}（{sanitize(article['source_category'])}）
**文章標題：** {sanitize(article['title'])}
**發布日期：** {article['pub_date'][:10]}
**原始連結：** {article['link']}

**摘要/內文片段：**
{sanitize(article.get('abstract', '')) or '（此來源未提供摘要，請根據標題進行分析）'}"""

    for attempt in range(retry + 1):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=1200,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}]
            )
            raw = response.content[0].text
            summary = extract_json(raw)

            if not summary:
                safe_print(f"      [WARN] JSON parse fail (attempt {attempt+1})")
                if attempt < retry:
                    time.sleep(3)
                    continue
                return None

            summary["original_title"] = article["title"]
            summary["link"] = article["link"]
            summary["source_name"] = article["source_name"]
            summary["source_category"] = article["source_category"]
            summary["source_color"] = article.get("source_color", "")
            summary["pub_date"] = article["pub_date"][:10]
            summary["id"] = article["id"]
            return summary

        except anthropic.RateLimitError:
            wait = 15 * (attempt + 1)
            safe_print(f"      [WARN] Rate limit, wait {wait}s...")
            time.sleep(wait)
        except Exception as e:
            safe_print(f"      [FAIL] {safe_str(e)}")
            if attempt < retry:
                time.sleep(5)
            else:
                return None
    return None


def main():
    safe_print("=" * 50)
    safe_print("[START] Generate AI summaries")
    safe_print("=" * 50)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        safe_print("[FAIL] ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    safe_print(f"  Model: {MODEL}")
    safe_print("  Testing API connection...")
    try:
        client.messages.create(
            model=MODEL,
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        safe_print("  [OK] API connection works")
    except anthropic.AuthenticationError:
        safe_print("  [FAIL] Invalid API key")
        sys.exit(1)
    except anthropic.NotFoundError:
        safe_print(f"  [FAIL] Model not found: {MODEL}")
        sys.exit(1)
    except Exception as e:
        safe_print(f"  [FAIL] API test failed: {safe_str(e)}")
        sys.exit(1)

    input_path = "data/fetched_articles.json"
    if not os.path.exists(input_path):
        safe_print(f"[FAIL] {input_path} not found")
        Path("data").mkdir(exist_ok=True)
        with open("data/summaries.json", "w", encoding="utf-8") as f:
            json.dump([], f)
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        articles = json.load(f)

    if not articles:
        safe_print("[SKIP] No articles (fetched_articles.json is empty)")
        with open("data/summaries.json", "w", encoding="utf-8") as f:
            json.dump([], f)
        return

    safe_print(f"  {len(articles)} articles to summarize")

    summaries = []
    for i, article in enumerate(articles, 1):
        title_ascii = article['title'][:60].encode('ascii', errors='replace').decode('ascii')
        safe_print(f"  [{i}/{len(articles)}] {title_ascii}")
        summary = summarize_article(client, article)
        if summary:
            summaries.append(summary)
            safe_print(f"      [OK] podcast_potential={summary.get('podcast_potential', 1)}")
        else:
            safe_print("      [SKIP]")
        if i < len(articles):
            time.sleep(2)

    summaries.sort(key=lambda x: x.get("podcast_potential", 1), reverse=True)

    output_path = "data/summaries.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2)

    safe_print(f"[OK] {len(summaries)} summaries saved to {output_path}")

    if summaries:
        safe_print("Top picks:")
        for s in summaries[:5]:
            t = s.get('title_zh', '').encode('ascii', errors='replace').decode('ascii')
            d = s.get('tldr', '').encode('ascii', errors='replace').decode('ascii')
            safe_print(f"  [{s.get('podcast_potential',1)}] {t}")
            safe_print(f"     {d}")


if __name__ == "__main__":
    main()
