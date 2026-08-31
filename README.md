# OkinawaSundays

面向繁體中文旅客的沖繩旅遊資訊平台。首頁回答「今天在沖繩可以做什麼」（天氣、今天是什麼日子、今日新聞、近期活動），底下是攻略、認識沖繩、好物、玩水四個內容區與活動年曆。

改版藍圖與分期規劃：[`SITE_PLAN.md`](SITE_PLAN.md)

## 網站結構

```
build.py                     站台產生器（templates + content + docs/*.json → docs/）
okinawa_events_crawler.py    抓活動與天氣，寫進 docs/events.json、docs/weather.json，最後呼叫 build_site()
news_crawler.py              抓沖繩新聞/日本大事 + 氣象警報，用 OpenAI 整理成繁中摘要，寫進 docs/news.json
rates_crawler.py             每日抓一次日圓匯率參考值，寫進 docs/rates.json
ocean_crawler.py             每 3 小時抓三個岸潛點的風/浪/潮汐，寫進 docs/ocean-conditions.json
templates/                   base.html + 各頁版型
assets/                      site.css / site.js / home.js / events.js / section.js / toolkit.js / ig-carousel.js
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

## 匯率換算（`rates_crawler.py`）

免金鑰的 `open.er-api.com`，每日 07:00 JST 由 `.github/workflows/rates.yml` 抓一次
日圓對台幣／港幣／美金／人民幣／韓元的參考匯率，寫進 `docs/rates.json`。
前端（`/toolkit/#rate`）純讀這份靜態 json 做即時換算，沒有任何 API key 暴露在前端。
抓取失敗會保留上一版，不會讓小工具消失或壞掉。

## 玩水海況（`ocean_crawler.py`）

三個熱門岸潛點（砂邊2號點、青の洞窟、大猩猩）的即時風向風力（`api.open-meteo.com`）
與浪高、湧浪、潮位（`marine-api.open-meteo.com`），全部免金鑰，每 3 小時由
`.github/workflows/ocean.yml` 更新一次，寫進 `docs/ocean-conditions.json`。

判斷邏輯是通用的岸潛安全經驗法則（風速／浪高門檻）疊加每個點自己的地形特性
（面對哪個方向、被什麼擋住，寫在 `ocean_crawler.py` 的 `SPOTS` 常數裡），
在 `/ocean/` 頁面上方render成三張卡片，並清楚標示「僅供參考，實際請以現場、
教練與官方公告為準」——尤其真栄田岬本身就有官方旗幟／即時影像系統，那才是
最終依據。搭配教學文章 `content/ocean/how-to-judge-conditions.md` 講風向、
風力、浪高、潮汐怎麼看，並用這三個點做對比案例。

## IG 產線

每篇文章的 front matter 只要有 `ig.slides`，就會在頁面產生一段橫向的「IG 輪播位」
（`assets/ig-carousel.js`）：捲動時卡片會即時做景深縮放與旋轉，下方有浮標可以直接點著跳頁，
尊重 `prefers-reduced-motion`（會退化成單純橫捲，不做 3D 變形）。
同一份資料也會彙整進 `docs/ig-queue.json`，是給 `SonaSNS-Platform/IGcarousell` 那支
輪播圖產生工具讀的待產清單（封面、逐頁文案、貼文文案、hashtag 都在裡面）。

> 待辦：`SonaSNS-Platform/IGcarousell` 目前只有一套偏文字的卡片視覺，還沒有「旅遊向、圖片多」
> 的版型。那是另一個專案裡的獨立設計任務，不在這支 build.py 的範圍內，需要另外排時間做。

## 好物頁的兩種內容

`/goods/` 中間是獨立單品卡片（`content/goods-items/*.md`：`name`/`emoji`/`blurb`/`where`/
`price`/`tags`，不需要內文），用「店舖類型」（超市/便利店/藥妝/100円/300円）與「好物類型」
（藥品/美妝/護膚/食品/手信/工藝品/酒類）兩軸篩選；下面才是完整文章（`content/goods/*.md`），
標題「深度好物指南」，不再重複篩選 UI。篩選邏輯在 `assets/section.js`，一個頁面可以有多組
互不干擾的篩選器＋格子，靠 `data-target` 對應。

## 首頁月份速覽

`content/months/01.md` ~ `12.md`：每月一篇速覽（`month`/`title`/`blurb`/`weather`/
`highlight`/內文），產生 `/guide/month-<n>/` 頁面，首頁天氣下方有 1-12 月橫排小卡，
滑過換預覽文字、點下去進當月詳細。7 月那篇會連到 `content/guide/july-okinawa.md`
那篇更完整的深度攻略（front matter 裡 `full_guide_slug` + 內文 `{{FULL_GUIDE_URL}}`
佔位字串會被換成正確連結）。

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

## 2026-08-02 進度

- 首頁排版收尾：Month by Month 移回 This Week's Weather 正下方；Know Okinawa（沖繩一年的祭典與年中行事）移到與 Travel Guide 並排（右側）。7/27 遺留的本機未提交修改已核對、重建 `docs/` 並提交。

## 品牌資料

品牌定位、色盤、語氣與內容架構見 `../SonaSNS-Platform/brands/OKIPLAYGROUND/BRAND_DNA.md`。

所有活動與安全資訊以原始來源最新公告為準。
