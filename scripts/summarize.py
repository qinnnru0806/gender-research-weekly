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

# ============================================================
# 編碼修復：GitHub Actions runner 預設 LANG=C (ASCII only)
# 必須在 import anthropic 之前就把環境設好
# ============================================================
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ.setdefault("LANG", "en_US.UTF-8")
os.environ.setdefault("LC_ALL", "en_US.UTF-8")

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import anthropic  # noqa: E402 — 必須在編碼設定之後 import


def safe_print(*args, **kwargs):
    """
    安全的 print：即使 stdout 是 ASCII 也不會炸。
    所有非 ASCII 字元會被替換成 '?'。
    """
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        text = " ".join(str(a) for a in args)
        print(text.encode("ascii", errors="replace").decode("ascii"), **kwargs)


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

# 使用 Sonnet 4.6：便宜、快、品質夠好
# 如果想要更高品質可改成 "claude-opus-4-6"（費用較高）
MODEL = "claude-sonnet-4-6"


def sanitize(text: str) -> str:
    """將特殊 Unicode 字元替換為安全字元"""
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


def to_ascii(text: str) -> str:
    """把任何字串轉成 ASCII safe（用於 print log）"""
    if not text:
        return ""
    return text.encode("ascii", errors="replace").decode("ascii")


def extract_json(raw: str) -> dict | None:
    """從 Claude 回應中提取 JSON"""
    text = raw.strip()

    # 移除 markdown code block
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
    """呼叫 Claude API 生成單篇摘要"""

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
                safe_print(f"      raw[:200]: {to_ascii(raw[:200])}")
                if attempt < retry:
                    time.sleep(3)
                    continue
                return None

            summary["original_title"] = article["title"]
            summary["link"] = article["link"]
            summary["source_name"] = article["source_name"]
            summary["source_category"] = article["source_category"]
            summary["source_color"] = article.get("source_color", "📄")
            summary["pub_date"] = article["pub_date"][:10]
            summary["id"] = article["id"]

            return summary

        except anthropic.RateLimitError:
            wait = 15 * (attempt + 1)
            safe_print(f"      [WARN] Rate limit, wait {wait}s...")
            time.sleep(wait)
        except anthropic.APIError as e:
            safe_print(f"      [FAIL] API error: {to_ascii(str(e))}")
            if attempt < retry:
                time.sleep(5)
            else:
                return None
        except Exception as e:
            safe_print(f"      [FAIL] Unexpected: {to_ascii(str(e))}")
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

    if not api_key.startswith("sk-ant-"):
        safe_print("[WARN] API key format looks wrong (should start with sk-ant-)")

    client = anthropic.Anthropic(api_key=api_key)

    # 測試 API 連線
    safe_print(f"  Model: {MODEL}")
    safe_print(f"  Testing API connection...")
    try:
        test_resp = client.messages.create(
            model=MODEL,
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        safe_print("  [OK] API connection works")
    except anthropic.AuthenticationError:
        safe_print("  [FAIL] Invalid API key")
        sys.exit(1)
    except anthropic.NotFoundError:
        safe_print(f"  [FAIL] Model '{MODEL}' not found")
        sys.exit(1)
    except Exception as e:
        safe_print(f"  [FAIL] API test failed: {to_ascii(str(e))}")
        sys.exit(1)

    # 讀取文章
    input_path = "data/fetched_articles.json"
    if not os.path.exists(input_path):
        safe_print(f"[FAIL] {input_path} not found, run fetch_sources.py first")
        Path("data").mkdir(exist_ok=True)
        with open("data/summaries.json", "w", encoding="utf-8") as f:
            json.dump([], f)
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        articles = json.load(f)

    if not articles:
        safe_print("[SKIP] No articles to summarize (fetched_articles.json is empty)")
        with open("data/summaries.json", "w", encoding="utf-8") as f:
            json.dump([], f)
        return

    safe_print(f"  {len(articles)} articles to summarize\n")

    summaries = []
    for i, article in enumerate(articles, 1):
        safe_print(f"  [{i}/{len(articles)}] {to_ascii(article['title'][:60])}")
        summary = summarize_article(client, article)
        if summary:
            summaries.append(summary)
            safe_print(f"      [OK] podcast_potential={summary.get('podcast_potential', 1)}")
        else:
            safe_print(f"      [SKIP]")

        if i < len(articles):
            time.sleep(2)

    summaries.sort(key=lambda x: x.get("podcast_potential", 1), reverse=True)

    output_path = "data/summaries.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2)

    safe_print(f"\n[OK] {len(summaries)} summaries saved to {output_path}")

    if summaries:
        safe_print("\nTop picks:")
        for s in summaries[:5]:
            safe_print(f"  [{s.get('podcast_potential',1)}] {to_ascii(s.get('title_zh',''))}")
            safe_print(f"     {to_ascii(s.get('tldr',''))}")
    else:
        safe_print("\n[WARN] All articles failed, check API key and model name")


if __name__ == "__main__":
    main()
