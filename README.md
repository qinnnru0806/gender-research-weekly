# 📚 性別研究週報系統
> 新世紀直男戰士 Podcast — 自動化研究摘要推播

每週一自動抓取最新性別研究論文，由 Claude AI 生成中文摘要，透過 LINE Bot 推播 Flex Message 輪播卡片，並同步更新 GitHub Pages 靜態存檔網站。

---

## 🏗️ 系統架構

```
GitHub Actions（每週一 09:00 台灣時間）
    ↓
fetch_sources.py   → 抓取 16 個學術期刊 RSS
    ↓
summarize.py       → Claude API 生成中文摘要
    ↓
generate_site.py   → 更新 GitHub Pages 網站
    ↓
notify_line.py     → LINE Bot 推播 Flex Message 輪播
```

---

## ⚙️ 部署步驟（30 分鐘完成）

### 步驟 1：Fork 這個 Repo

點擊右上角 **Fork**，建立你自己的副本。

### 步驟 2：取得三個 Token

#### A. Anthropic API Key
1. 前往 [console.anthropic.com](https://console.anthropic.com)
2. API Keys → Create Key
3. 複製 `sk-ant-...` 開頭的金鑰

#### B. 建立新的 LINE Bot Channel（在既有 Provider 下新增）

> LINE 的帳號結構是：**個人 LINE 帳號 → LINE Developers 帳號 → Provider → Channel（Bot）**
> 你不需要申請新帳號，直接在既有的 Provider 下新增一個 Channel 就好，不影響舊的 Bot。

1. 前往 [LINE Developers Console](https://developers.line.biz)，用你原本的 LINE 帳號登入
2. 左側選單點進你原有的 **Provider**（例如你之前建 Bot 用的那個）
3. 點右上角 **Create a new channel**
4. Channel type 選 **Messaging API**
5. 填入基本資料：
   - Channel name：例如「性別研究週報」
   - Channel description：隨意填
   - Category / Subcategory：選 Education 或其他合適的
6. 勾選同意條款 → 點 **Create**
7. 進入新 Channel → 切換到 **Messaging API** 分頁
8. 滾到最底部 **Channel access token** → 點 **Issue**
9. 複製這串長 Token（之後填入 GitHub Secrets 的 `LINE_CHANNEL_TOKEN`）

> 💡 建立後記得在 **Basic settings** 分頁把 Bot 的大頭貼和名稱設定好，這樣加入群組時看起來比較正式。

#### C. 取得 LINE 群組 ID

這步需要讓 Bot 先加入群組、接收一次 webhook event 才能拿到群組 ID。

**第一步：開啟 Webhook**
1. 在新 Channel 的 **Messaging API** 分頁，找到 **Webhook URL** 欄位
2. 目前先不用填 URL，但要把 **Use webhook** 打開（toggle 開啟）

**第二步：建立一個臨時 webhook 接收器**
1. 前往 [https://webhook.site](https://webhook.site)，它會給你一個臨時 URL（像 `https://webhook.site/xxxxxxxx`）
2. 複製這個 URL，貼回 LINE Developers Console 的 **Webhook URL** 欄位
3. 點 **Verify** 確認連線成功（顯示 200 OK）

**第三步：把 Bot 加入群組並觸發事件**
1. 在 LINE Developers Console → **Messaging API** 分頁，找到 **Bot basic ID**（格式是 `@xxxx`）
2. 在 LINE App 裡，進入你要推播的群組
3. 點群組右上角「成員」→「邀請」→ 搜尋你的 Bot ID（`@xxxx`）→ 邀請加入
4. Bot 加入後，**在群組裡隨意發一則訊息**（任何內容都可以）

**第四步：從 webhook.site 取得群組 ID**
1. 回到 [https://webhook.site](https://webhook.site)，你會看到剛才觸發的 webhook event JSON
2. 在 JSON 裡找這個結構：
   ```json
   "source": {
     "type": "group",
     "groupId": "Cxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
   }
   ```
3. 複製 `groupId` 的值（`C` 開頭的 33 碼），這就是你要的群組 ID

**第五步：清除臨時 Webhook URL**
取得 group ID 後，記得回 LINE Developers Console 把 Webhook URL 清空或換成正式的（本系統是主動推播，不需要固定 webhook URL 也能運作）。

### 步驟 3：設定 GitHub Secrets

在你的 Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

新增以下 4 個 Secrets：

| Secret 名稱 | 值 |
|-------------|-----|
| `ANTHROPIC_API_KEY` | `sk-ant-...` |
| `LINE_CHANNEL_TOKEN` | LINE Bot 的 Channel Token |
| `LINE_GROUP_ID` | `C...` 開頭的群組 ID |
| `SITE_URL` | `https://你的帳號.github.io/gender-research-weekly` |

### 步驟 4：啟用 GitHub Pages

1. Repo → **Settings** → **Pages**
2. Source 選 **Deploy from a branch**
3. Branch 選 **main**，Folder 選 **/ (root)** 或 **/docs**
4. 選 `/docs`，點 **Save**

### 步驟 5：手動觸發一次測試

1. Repo → **Actions** → **週報自動推播**
2. 右側 **Run workflow** → `dry_run` 選 `true`（先不推播 LINE，只測試抓取和摘要）
3. 點 **Run workflow**
4. 等待約 3-5 分鐘完成
5. 確認 Actions log 沒有紅色錯誤
6. 確認 `docs/index.html` 有被更新

### 步驟 6：真正推播測試

確認 dry run 成功後：
1. 再次手動觸發，`dry_run` 選 `false`
2. 確認 LINE 群組收到訊息

---

## 📁 檔案結構

```
gender-research-weekly/
├── .github/
│   └── workflows/
│       └── weekly.yml          # 排程設定
├── scripts/
│   ├── fetch_sources.py        # RSS 抓取
│   ├── summarize.py            # Claude AI 摘要生成
│   ├── notify_line.py          # LINE Bot 推播
│   └── generate_site.py       # 靜態網站生成
├── docs/                       # GitHub Pages 輸出（自動生成）
│   ├── index.html              # 最新週報
│   └── ????W??.html            # 歷史週報
├── data/                       # 中間資料（自動生成）
│   ├── fetched_articles.json   # 本週抓取文章
│   ├── summaries.json          # 本週 AI 摘要
│   ├── seen_ids.json           # 已推播 ID（去重用）
│   └── weekly/                 # 推播紀錄
├── sources.yaml                # 來源設定（你來維護）
├── requirements.txt            # Python 套件
└── README.md
```

---

## 🛠️ 日常維護

### 新增來源
直接編輯 `sources.yaml`，在對應類別下新增：
```yaml
- name: "新期刊名稱"
  url: "RSS URL"
  category: "男性研究"
  color: "🔵"
```

### 調整推播篇數
`sources.yaml` 頂部：
```yaml
line_push_count: 5   # 改成你要的數字
```

### 調整抓取天數
```yaml
days_lookback: 7   # 只抓7天內的新文章
```

### 手動觸發（任何時候想要更新）
Actions → 週報自動推播 → Run workflow

---

## 💰 費用估算

| 項目 | 費用 |
|------|------|
| GitHub Actions | 免費（每月 2000 分鐘，每次跑約 5 分鐘） |
| GitHub Pages | 免費 |
| LINE Bot 推播 | 免費（每月 < 200 則） |
| Anthropic API | 每週約 NT$15-30（8 篇 × claude-opus-4） |
| **合計** | **約 NT$60-120 / 月** |

---

## ❓ 常見問題

**Q：Actions 跑完但 LINE 沒收到訊息？**
A：檢查 `LINE_GROUP_ID` 是否正確，Bot 是否還在群組內。

**Q：摘要品質不好怎麼辦？**
A：可以編輯 `scripts/summarize.py` 裡的 `SYSTEM_PROMPT`，調整風格要求。

**Q：某個 RSS 抓不到資料？**
A：直接在 Actions log 搜尋 `❌`，找到失敗的來源，確認 URL 是否有效。

**Q：想增加 YouTube 影片摘要？**
A：下一個版本功能，需要 YouTube Data API key，可以另外討論。

---

## 📝 版本紀錄

**v1.0** — 初版
- 16 個學術期刊 RSS 抓取
- Claude AI 中文摘要（含台灣脈絡與小編評語）
- LINE Bot Flex Message 輪播推播
- GitHub Pages 靜態存檔網站
