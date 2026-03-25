#!/usr/bin/env python3
"""
notify_line.py
透過 LINE Messaging API 推播 Flex Message 輪播卡片到群組
"""

import json
import os
import requests
import yaml
from datetime import datetime
from pathlib import Path


LINE_API_URL = "https://api.line.me/v2/bot/message/push"


def load_config() -> dict:
    with open("sources.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_week_number() -> str:
    """取得本年第幾週"""
    now = datetime.now()
    return f"{now.year}W{now.isocalendar()[1]:02d}"


def category_emoji(category: str) -> str:
    mapping = {
        "男性研究": "🔵",
        "女性研究": "🔴",
        "同志研究": "🟡",
        "跨性別研究": "🟢",
        "跨類別": "🟣",
        "台灣本地": "🇹🇼",
    }
    return mapping.get(category, "📄")


def star_rating(score: int) -> str:
    return "★" * score + "☆" * (5 - score)


def build_bubble(summary: dict, index: int, total: int) -> dict:
    """建立單張 Flex Message 卡片"""

    color_map = {
        "男性研究": "#2196F3",
        "女性研究": "#E91E63",
        "同志研究": "#FFC107",
        "跨性別研究": "#4CAF50",
        "跨類別": "#9C27B0",
        "台灣本地": "#FF5722",
    }
    header_color = color_map.get(summary.get("source_category", ""), "#607D8B")

    # 主要發現列表
    findings_contents = []
    for finding in summary.get("key_findings", [])[:3]:
        findings_contents.append({
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "text",
                    "text": "•",
                    "size": "sm",
                    "color": "#888888",
                    "flex": 0,
                    "margin": "none"
                },
                {
                    "type": "text",
                    "text": finding,
                    "size": "sm",
                    "color": "#555555",
                    "wrap": True,
                    "flex": 1,
                    "margin": "sm"
                }
            ],
            "margin": "sm"
        })

    bubble = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": f"{category_emoji(summary.get('source_category', ''))} {summary.get('source_category', '研究')}",
                            "size": "xs",
                            "color": "#ffffff",
                            "flex": 1
                        },
                        {
                            "type": "text",
                            "text": f"{index}/{total}",
                            "size": "xs",
                            "color": "#ffffff99",
                            "align": "end",
                            "flex": 0
                        }
                    ]
                },
                {
                    "type": "text",
                    "text": summary.get("title_zh", "（翻譯中）"),
                    "weight": "bold",
                    "size": "md",
                    "color": "#ffffff",
                    "wrap": True,
                    "margin": "sm",
                    "maxLines": 3
                },
                {
                    "type": "text",
                    "text": f"💬 {summary.get('tldr', '')}",
                    "size": "xs",
                    "color": "#ffffffcc",
                    "wrap": True,
                    "margin": "sm"
                }
            ],
            "backgroundColor": header_color,
            "paddingAll": "16px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                # 來源與日期
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": summary.get("source_name", ""),
                            "size": "xxs",
                            "color": "#aaaaaa",
                            "flex": 1,
                            "wrap": True
                        },
                        {
                            "type": "text",
                            "text": summary.get("pub_date", ""),
                            "size": "xxs",
                            "color": "#aaaaaa",
                            "align": "end",
                            "flex": 0
                        }
                    ],
                    "margin": "none"
                },
                # 節目潛力
                {
                    "type": "text",
                    "text": f"節目潛力 {star_rating(summary.get('podcast_potential', 1))}",
                    "size": "xxs",
                    "color": "#F5A623",
                    "margin": "sm"
                },
                # 分隔線
                {
                    "type": "separator",
                    "margin": "md",
                    "color": "#eeeeee"
                },
                # 主要發現
                {
                    "type": "text",
                    "text": "🔍 主要發現",
                    "size": "sm",
                    "weight": "bold",
                    "color": "#333333",
                    "margin": "md"
                },
                *findings_contents,
                # 分隔線
                {
                    "type": "separator",
                    "margin": "md",
                    "color": "#eeeeee"
                },
                # 台灣脈絡
                {
                    "type": "text",
                    "text": "🇹🇼 台灣怎麼看",
                    "size": "sm",
                    "weight": "bold",
                    "color": "#333333",
                    "margin": "md"
                },
                {
                    "type": "text",
                    "text": summary.get("taiwan_context", ""),
                    "size": "sm",
                    "color": "#555555",
                    "wrap": True,
                    "margin": "sm"
                },
                # 分隔線
                {
                    "type": "separator",
                    "margin": "md",
                    "color": "#eeeeee"
                },
                # 小編評語
                {
                    "type": "text",
                    "text": "✍️ 小編有話說",
                    "size": "sm",
                    "weight": "bold",
                    "color": "#333333",
                    "margin": "md"
                },
                {
                    "type": "text",
                    "text": summary.get("editor_note", ""),
                    "size": "sm",
                    "color": "#555555",
                    "wrap": True,
                    "margin": "sm"
                }
            ],
            "paddingAll": "16px",
            "spacing": "none"
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "uri",
                        "label": "閱讀原文",
                        "uri": summary.get("link", "https://example.com")
                    },
                    "style": "primary",
                    "color": header_color,
                    "height": "sm"
                }
            ],
            "paddingAll": "12px"
        }
    }

    return bubble


def build_carousel(summaries: list, week_id: str, site_url: str) -> dict:
    """建立輪播 Flex Message"""

    # 最多 12 張（LINE 限制），我們取 5 張
    selected = summaries[:5]
    total = len(selected)

    bubbles = [build_bubble(s, i + 1, total) for i, s in enumerate(selected)]

    # 最後加一張「看完整週報」卡片
    site_bubble = {
        "type": "bubble",
        "size": "mega",
        "body": {
            "type": "box",
            "layout": "vertical",
            "justifyContent": "center",
            "contents": [
                {
                    "type": "text",
                    "text": "📚",
                    "size": "5xl",
                    "align": "center"
                },
                {
                    "type": "text",
                    "text": "看完整週報",
                    "weight": "bold",
                    "size": "lg",
                    "align": "center",
                    "margin": "md"
                },
                {
                    "type": "text",
                    "text": f"本週共 {total} 篇精選\n包含完整摘要與歷史存檔",
                    "size": "sm",
                    "color": "#888888",
                    "align": "center",
                    "wrap": True,
                    "margin": "sm"
                }
            ],
            "paddingAll": "32px"
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "uri",
                        "label": "前往週報網站",
                        "uri": site_url
                    },
                    "style": "primary",
                    "color": "#607D8B"
                }
            ],
            "paddingAll": "12px"
        }
    }
    bubbles.append(site_bubble)

    return {
        "type": "flex",
        "altText": f"📚 性別研究週報 {week_id}｜本週精選 {total} 篇",
        "contents": {
            "type": "carousel",
            "contents": bubbles
        }
    }


def send_to_line(group_id: str, channel_token: str, messages: list) -> bool:
    """發送訊息到 LINE 群組"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {channel_token}"
    }
    payload = {
        "to": group_id,
        "messages": messages
    }

    response = requests.post(LINE_API_URL, headers=headers, json=payload)

    if response.status_code == 200:
        print("✅ LINE 推播成功")
        return True
    else:
        print(f"❌ LINE 推播失敗：{response.status_code} {response.text}")
        return False


def main():
    print("📲 開始推播 LINE 訊息...\n")

    # 環境變數
    channel_token = os.environ.get("LINE_CHANNEL_TOKEN")
    group_id = os.environ.get("LINE_GROUP_ID")
    site_url = os.environ.get("SITE_URL", "https://yourusername.github.io/gender-research-weekly")

    if not channel_token or not group_id:
        raise ValueError("請設定 LINE_CHANNEL_TOKEN 和 LINE_GROUP_ID 環境變數")

    # 讀取摘要
    summary_path = "data/summaries.json"
    if not os.path.exists(summary_path):
        print("❌ 找不到 summaries.json，請先執行 summarize.py")
        return

    with open(summary_path, "r", encoding="utf-8") as f:
        summaries = json.load(f)

    if not summaries:
        print("⚠️ 本週沒有摘要，跳過推播")
        return

    week_id = get_week_number()
    config = load_config()
    push_count = config.get("line_push_count", 5)
    top_summaries = summaries[:push_count]

    print(f"  週次：{week_id}")
    print(f"  推播篇數：{len(top_summaries)}")
    print(f"  最高潛力：{top_summaries[0]['title_zh']}")

    # 建立前置文字訊息（週報引言）
    categories = list(set(s.get("source_category", "") for s in top_summaries))
    categories_str = "、".join(categories[:3])

    intro_message = {
        "type": "text",
        "text": (
            f"📚 性別研究週報 {week_id}\n"
            f"━━━━━━━━━━━━━━\n"
            f"本週精選 {len(top_summaries)} 篇，涵蓋：{categories_str}\n\n"
            f"👇 左右滑動查看每篇摘要"
        )
    }

    # 建立 Flex Message 輪播
    carousel_message = build_carousel(top_summaries, week_id, site_url)

    # 推播
    success = send_to_line(group_id, channel_token, [intro_message, carousel_message])

    if success:
        # 儲存本次推播紀錄
        push_log = {
            "week_id": week_id,
            "pushed_at": datetime.now().isoformat(),
            "count": len(top_summaries),
            "titles": [s["title_zh"] for s in top_summaries]
        }
        log_path = f"data/weekly/push_log_{week_id}.json"
        Path("data/weekly").mkdir(parents=True, exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(push_log, f, ensure_ascii=False, indent=2)
        print(f"\n📝 推播紀錄已儲存：{log_path}")


if __name__ == "__main__":
    main()
