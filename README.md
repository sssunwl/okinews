# OKIPLAYGROUND 沖繩遊樂園

面向繁體中文旅客的沖繩旅遊資訊平台。首頁回答「今天在沖繩可以做什麼」（天氣、今天是什麼日子、今日新聞、近期活動），底下是攻略、認識沖繩、好物、玩水四個內容區與活動年曆。

改版藍圖與分期規劃：[`SITE_PLAN.md`](SITE_PLAN.md)

## 網站結構

```
build.py                     站台產生器（templates + content + docs/*.json → docs/）
okinawa_events_crawler.py    抓活動與天氣，寫進 docs/events.json、docs/weather.json，最後呼叫 build_site()
news_crawler.py              抓沖繩新聞/日本大事 + 氣象警報，用 OpenAI 整理成繁中摘要，寫進 docs/news.json
templates/                   base.html + 各頁版型
assets/                      site.css / site.js / home.js / events.js / section.js / toolkit.js
content/<section>/*.md       文章內容（front matter + Markdown）
content/covers/              文章封面圖（build 時複製到 docs/assets/covers/）
docs/                        GitHub Pages 產物，不要手改
```

產出頁面：`/`、`/news/`、`/events/`、`/guide/`、`/okinawa/`、`/goods/`、`/ocean/`、`/toolkit/`，
以及每篇文章的 `/<section>/<slug>/`。另外產生 `sitemap.xml`、`robots.txt`、
`ig-queue.json`（IG 輪播待產清單）與 `build-report.json`（哪些內容被跳過）。

## 本機預覽

```bash
python3 build.py                      # 只重建網頁，不重新爬資料
BUILD_ONLY=1 python3 okinawa_events_crawler.py   # 重算「今天是…」再重建
python3 news_crawler.py               # 抓新聞 + 氣象警報（需要 OPENAI_API_KEY，見下）
python3 -m http.server 8000 --directory docs
```

## 新聞自動化（`news_crawler.py`）

來源：沖縄タイムス RSS（在地新聞）、NHK 主要ニュース RSS（日本大事）、
気象庁 警報・注意報 JSON（沖繩本島／大東／宮古／八重山四個地方）。
每則交給 OpenAI（`gpt-5.4-mini`）整理成繁中標題＋2-3 句摘要＋分類＋是否影響旅客（`alert`），
每日 07:30 JST 由 `.github/workflows/news.yml` 自動跑（GitHub Actions secret：`OPENAI_API_KEY`）。

全自動發佈，所以機器關卡在程式裡：缺欄位、非 `https` 連結、摘要超長的項目直接跳過
（記在 `docs/news-report.json`）；整批抓不到新東西時保留上一版 `docs/news.json`，
不產生空白頁；氣象警報每次重新產生，「解除」的不會標成 `alert`。
只做短摘要與原文連結，不做全文翻譯轉載。

本機測試需要 `~/.config/openai/credentials.json`（`{"api_key": "sk-..."}`），
或設定 `OPENAI_API_KEY` 環境變數；沒有 key 時會優雅退化成只重建網頁。

**琉球新報目前沒有公開 RSS**（`/feed/` 會 301 導回首頁），暫時沒收進來源；
如果之後找到可用端點，加進 `news_crawler.py` 的 `fetch_rss` 呼叫即可。

## 寫一篇新文章

在 `content/<section>/` 放一個 `.md`，front matter 規格：

```yaml
---
title: 標題
slug: url-slug              # 只能小寫英數與連字號
summary: 一句話摘要
tags: [玩, 一天遊, 那霸]      # 要對得上 build.py 的 SECTIONS[...]["axes"] 才會出現篩選 chip
cover: naha.jpg             # 選填，放在 content/covers/
updated: 2026-07-26
ig:                         # 選填；有 slides 才會產生 IG 位與 ig-queue 條目
  cover: 封面標題
  slides:
    - 第一頁
    - 第二頁
  caption: |
    貼文文案
  hashtags: [沖繩自由行]
---
正文 Markdown（支援標題、清單、引言、表格、連結、圖片）
```

**內容全自動發佈**，所以 build 時有機器關卡：缺 title / summary / 內文、slug 格式錯、
日期格式錯的檔案會被跳過而不是產出半成品，跳過原因記在 `docs/build-report.json`。

## 品牌資料

品牌定位、色盤、語氣與內容架構見 `../SonaSNS-Platform/brands/OKIPLAYGROUND/BRAND_DNA.md`。

所有活動與安全資訊以原始來源最新公告為準。
