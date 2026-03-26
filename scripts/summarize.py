#!/usr/bin/env python3
"""
summarize.py
呼叫 Claude API，為每篇文章生成中文摘要（含台灣脈絡分析與小編評語）

修復重點：
1. 使用正確的 model 名稱 (claude-sonnet-4-20250514)
2. API 呼叫加入 retry 機制
3. 更完整的 JSON 解析錯誤處理
4. 空文章列表不再靜默跳過，而是明確提示
"""

import anthropic
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

# 強制設定 stdout/stderr 為 UTF-8
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


def extract_json(raw: str) -> dict | None:
    """從 Claude 回應中提取 JSON，處理各種格式問題"""
    text = raw.strip()

    # 移除 markdown code block
    if text.startswith("```"):
        lines = text.split("\n")
        # 去掉第一行 (```json) 和最後一行 (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    # 嘗試找到 JSON 物件的範圍
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        text = text[start:end]

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def summarize_article(client: anthropic.Anthropic, article: dict, retry: int = 2) -> dict | None:
    """呼叫 Claude API 生成單篇摘要，含 retry"""

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
                print(f"      [WARN] JSON 解析失敗（第 {attempt+1} 次）")
                print(f"      回應前 200 字: {raw[:200]}")
                if attempt < retry:
                    time.sleep(3)
                    continue
                return None

            # 附上原始資訊
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
            print(f"      [WARN] Rate limit，等 {wait}s...")
            time.sleep(wait)
        except anthropic.APIError as e:
            print(f"      [FAIL] API 錯誤: {e}")
            if attempt < retry:
                time.sleep(5)
            else:
                return None
        except Exception as e:
            print(f"      [FAIL] 未預期錯誤: {e}")
            return None

    return None


def main():
    print("=" * 50)
    print("[START] 生成 AI 摘要")
    print("=" * 50 + "\n")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ 未設定 ANTHROPIC_API_KEY 環境變數")
        print("   請在 GitHub Secrets 中設定，或本機執行時 export ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    # 驗證 API key 格式
    if not api_key.startswith("sk-ant-"):
        print(f"⚠️  API key 格式看起來不對（應以 sk-ant- 開頭），但仍嘗試呼叫...")

    client = anthropic.Anthropic(api_key=api_key)

    # 先測試 API 連線
    print(f"  使用模型: {MODEL}")
    print(f"  測試 API 連線...")
    try:
        test_resp = client.messages.create(
            model=MODEL,
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        print(f"  ✅ API 連線正常\n")
    except anthropic.AuthenticationError:
        print(f"  ❌ API key 無效！請確認 ANTHROPIC_API_KEY 是否正確")
        sys.exit(1)
    except anthropic.NotFoundError:
        print(f"  ❌ 模型 '{MODEL}' 不存在！請確認模型名稱")
        sys.exit(1)
    except Exception as e:
        print(f"  ❌ API 測試失敗: {e}")
        sys.exit(1)

    # 讀取抓取到的文章
    input_path = "data/fetched_articles.json"
    if not os.path.exists(input_path):
        print(f"❌ 找不到 {input_path}")
        print("   請先執行 fetch_sources.py")
        # 建立空摘要避免後續步驟報錯
        Path("data").mkdir(exist_ok=True)
        with open("data/summaries.json", "w", encoding="utf-8") as f:
            json.dump([], f)
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        articles = json.load(f)

    if not articles:
        print("⚠️  本週沒有新文章（fetched_articles.json 是空的）")
        print("   這代表 fetch_sources.py 沒有抓到任何文章")
        print("   可能原因：RSS feed 被擋、期刊本週沒更新、days_lookback 太短")
        with open("data/summaries.json", "w", encoding="utf-8") as f:
            json.dump([], f)
        return

    print(f"  共 {len(articles)} 篇待摘要\n")

    summaries = []
    for i, article in enumerate(articles, 1):
        safe_title = article['title'][:60]
        print(f"  [{i}/{len(articles)}] {safe_title}")
        summary = summarize_article(client, article)
        if summary:
            summaries.append(summary)
            print(f"      ✅ 完成 (podcast_potential: {summary.get('podcast_potential', 1)})")
        else:
            print(f"      ❌ 跳過")

        # 避免 rate limit
        if i < len(articles):
            time.sleep(2)

    # 按節目潛力排序
    summaries.sort(key=lambda x: x.get("podcast_potential", 1), reverse=True)

    output_path = "data/summaries.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 共生成 {len(summaries)} 篇摘要 → {output_path}")

    if summaries:
        print("\n📋 本週精選：")
        for s in summaries[:5]:
            print(f"   [{s.get('podcast_potential',1)}★] {s['title_zh']}")
            print(f"      → {s['tldr']}")
    else:
        print("\n⚠️  所有文章都摘要失敗，請檢查 API key 和模型名稱")


if __name__ == "__main__":
    main()
