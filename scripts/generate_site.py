#!/usr/bin/env python3
"""
generate_site.py
從 summaries.json 生成靜態 HTML 網站（部署到 GitHub Pages）
"""

import json
import os
from datetime import datetime
from pathlib import Path


def get_week_number() -> str:
    now = datetime.now()
    return f"{now.year}W{now.isocalendar()[1]:02d}"


def star_html(score: int) -> str:
    return "★" * score + "☆" * (5 - score)


def category_color(category: str) -> str:
    mapping = {
        "男性研究": "#2196F3",
        "女性研究": "#E91E63",
        "同志研究": "#FFC107",
        "跨性別研究": "#4CAF50",
        "跨類別": "#9C27B0",
        "台灣本地": "#FF5722",
    }
    return mapping.get(category, "#607D8B")


def build_article_card(summary: dict) -> str:
    cat = summary.get("source_category", "研究")
    color = category_color(cat)
    findings_html = "".join(
        f'<li>{f}</li>' for f in summary.get("key_findings", [])
    )

    return f"""
<article class="card" data-category="{cat}">
  <div class="card-header" style="border-left: 4px solid {color}">
    <span class="badge" style="background:{color}">{summary.get('source_color','📄')} {cat}</span>
    <span class="podcast-score" title="節目潛力">{star_html(summary.get('podcast_potential', 1))}</span>
    <h2 class="card-title">{summary.get('title_zh', '（翻譯中）')}</h2>
    <p class="tldr">💬 {summary.get('tldr', '')}</p>
    <div class="meta">
      <span>📄 {summary.get('source_name','')}</span>
      <span>📅 {summary.get('pub_date','')}</span>
    </div>
  </div>
  <div class="card-body">
    <section>
      <h3>🔍 主要發現</h3>
      <ul>{findings_html}</ul>
    </section>
    <section>
      <h3>🇹🇼 台灣怎麼看</h3>
      <p>{summary.get('taiwan_context', '')}</p>
    </section>
    <section>
      <h3>✍️ 小編有話說</h3>
      <p class="editor-note">{summary.get('editor_note', '')}</p>
    </section>
    <a href="{summary.get('link','#')}" target="_blank" rel="noopener" class="btn">
      閱讀原文 →
    </a>
  </div>
</article>"""


def build_html(summaries: list, week_id: str, all_weeks: list) -> str:
    cards_html = "\n".join(build_article_card(s) for s in summaries)

    # 週次選單
    week_options = "\n".join(
        f'<option value="{w}" {"selected" if w == week_id else ""}>{w}</option>'
        for w in all_weeks
    )

    categories = sorted(set(s.get("source_category", "") for s in summaries))
    filter_btns = '<button class="filter-btn active" data-cat="all">全部</button>\n' + "\n".join(
        f'<button class="filter-btn" data-cat="{c}" style="border-color:{category_color(c)}">{c}</button>'
        for c in categories
    )

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>性別研究週報｜新世紀直男戰士</title>
  <style>
    :root {{
      --bg: #f8f9fa;
      --card-bg: #ffffff;
      --text: #333333;
      --text-muted: #888888;
      --border: #eeeeee;
      --accent: #6200ea;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, "Noto Sans TC", sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.6;
    }}
    header {{
      background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
      color: white;
      padding: 2rem 1.5rem;
      text-align: center;
    }}
    header h1 {{ font-size: 1.5rem; font-weight: 700; margin-bottom: 0.5rem; }}
    header p {{ font-size: 0.9rem; opacity: 0.8; }}
    .toolbar {{
      background: white;
      border-bottom: 1px solid var(--border);
      padding: 1rem 1.5rem;
      display: flex;
      gap: 1rem;
      align-items: center;
      flex-wrap: wrap;
      position: sticky;
      top: 0;
      z-index: 100;
    }}
    .week-select {{
      padding: 0.4rem 0.8rem;
      border: 1px solid var(--border);
      border-radius: 6px;
      font-size: 0.85rem;
      cursor: pointer;
    }}
    .filter-btn {{
      padding: 0.3rem 0.8rem;
      border: 1px solid var(--border);
      border-radius: 20px;
      background: white;
      font-size: 0.8rem;
      cursor: pointer;
      transition: all 0.2s;
    }}
    .filter-btn.active, .filter-btn:hover {{
      background: var(--text);
      color: white;
      border-color: var(--text);
    }}
    .main {{
      max-width: 800px;
      margin: 0 auto;
      padding: 1.5rem;
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
    }}
    .card {{
      background: var(--card-bg);
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 2px 8px rgba(0,0,0,0.06);
      transition: transform 0.2s;
    }}
    .card:hover {{ transform: translateY(-2px); }}
    .card-header {{
      padding: 1.25rem 1.5rem 1rem;
      border-bottom: 1px solid var(--border);
    }}
    .badge {{
      display: inline-block;
      color: white;
      font-size: 0.75rem;
      padding: 0.15rem 0.6rem;
      border-radius: 20px;
      margin-bottom: 0.5rem;
    }}
    .podcast-score {{
      float: right;
      font-size: 0.75rem;
      color: #F5A623;
    }}
    .card-title {{
      font-size: 1.05rem;
      font-weight: 700;
      line-height: 1.4;
      margin: 0.5rem 0;
    }}
    .tldr {{
      font-size: 0.85rem;
      color: #555;
      margin-bottom: 0.5rem;
      font-style: italic;
    }}
    .meta {{
      display: flex;
      gap: 1rem;
      font-size: 0.75rem;
      color: var(--text-muted);
    }}
    .card-body {{
      padding: 1.25rem 1.5rem;
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }}
    .card-body h3 {{
      font-size: 0.85rem;
      font-weight: 700;
      margin-bottom: 0.4rem;
      color: #444;
    }}
    .card-body p, .card-body li {{
      font-size: 0.9rem;
      color: #555;
    }}
    .card-body ul {{ padding-left: 1.2rem; }}
    .card-body li {{ margin-bottom: 0.25rem; }}
    .editor-note {{
      background: #fafafa;
      border-left: 3px solid #ddd;
      padding: 0.75rem;
      border-radius: 0 6px 6px 0;
      font-size: 0.875rem !important;
    }}
    .btn {{
      display: inline-block;
      padding: 0.6rem 1.2rem;
      background: #1a1a2e;
      color: white;
      text-decoration: none;
      border-radius: 6px;
      font-size: 0.85rem;
      margin-top: 0.5rem;
      transition: opacity 0.2s;
    }}
    .btn:hover {{ opacity: 0.85; }}
    .empty {{ text-align: center; color: var(--text-muted); padding: 3rem; }}
    footer {{
      text-align: center;
      padding: 2rem;
      font-size: 0.8rem;
      color: var(--text-muted);
      border-top: 1px solid var(--border);
      margin-top: 2rem;
    }}
  </style>
</head>
<body>
  <header>
    <h1>📚 性別研究週報</h1>
    <p>新世紀直男戰士｜每週自動整理最新性別研究</p>
  </header>

  <div class="toolbar">
    <select class="week-select" onchange="changeWeek(this.value)">
      {week_options}
    </select>
    <div style="display:flex;gap:0.5rem;flex-wrap:wrap">
      {filter_btns}
    </div>
  </div>

  <main class="main" id="cards-container">
    {cards_html}
  </main>

  <footer>
    <p>🤖 由 Claude AI 自動生成摘要｜最後更新：{generated_at}</p>
    <p style="margin-top:0.5rem">新世紀直男戰士 Podcast｜摘要僅供參考，研究詮釋以原文為準</p>
  </footer>

  <script>
    // 分類篩選
    document.querySelectorAll('.filter-btn').forEach(btn => {{
      btn.addEventListener('click', function() {{
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        this.classList.add('active');
        const cat = this.dataset.cat;
        document.querySelectorAll('.card').forEach(card => {{
          card.style.display = (cat === 'all' || card.dataset.category === cat) ? '' : 'none';
        }});
      }});
    }});

    // 週次切換（預留，完整實作需要多個 JSON 檔）
    function changeWeek(week) {{
      window.location.href = week + '.html';
    }}
  </script>
</body>
</html>"""


def main():
    print("🌐 開始生成靜態網站...\n")

    week_id = get_week_number()
    docs_dir = Path("docs")
    docs_dir.mkdir(exist_ok=True)

    # 讀取摘要
    summary_path = "data/summaries.json"
    if not os.path.exists(summary_path):
        print("❌ 找不到 summaries.json")
        return

    with open(summary_path, "r", encoding="utf-8") as f:
        summaries = json.load(f)

    # 儲存本週摘要 JSON（供網站 JS 使用）
    week_json_path = docs_dir / f"{week_id}.json"
    with open(week_json_path, "w", encoding="utf-8") as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2)

    # 蒐集所有週次（用於下拉選單）
    all_weeks = sorted(
        [f.stem for f in docs_dir.glob("????W??.json")],
        reverse=True
    )
    if week_id not in all_weeks:
        all_weeks.insert(0, week_id)

    # 生成本週 HTML
    html = build_html(summaries, week_id, all_weeks)

    # 同時輸出 index.html（最新週）和 {week_id}.html
    for fname in ["index.html", f"{week_id}.html"]:
        path = docs_dir / fname
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  ✅ 已生成 {path}")

    print(f"\n✅ 網站生成完成（本週 {len(summaries)} 篇）")


if __name__ == "__main__":
    main()
