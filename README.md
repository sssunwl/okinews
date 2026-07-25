# OKIPLAYGROUND 沖繩遊樂園

面向繁體中文旅客的沖繩旅遊資訊平台。網站以「今天，在沖繩玩什麼？」為主題，將官方活動、文化節日與在地提醒整理成可搜尋、可收藏的互動年曆。

## 網站結構

- `site_template.html`：公開網站唯一頁面模板。
- `okinawa_events_crawler.py`：爬取活動、合併「今天是…」內容並生成網站。
- `docs/events.json`：目前的活動資料。
- `docs/index.html`：GitHub Pages 產物。
- `.github/workflows/crawler.yml`：每日 08:00 JST 更新資料。

## 本機預覽

只重新生成既有資料，不重新爬取：

```bash
BUILD_ONLY=1 python3 okinawa_events_crawler.py
python3 -m http.server 8000
```

瀏覽 `http://127.0.0.1:8000/docs/`。

## 品牌資料

品牌定位、色盤、語氣與內容架構見：

`../SonaSNS-Platform/brands/OKIPLAYGROUND/BRAND_DNA.md`

所有活動與安全資訊以原始來源最新公告為準。
