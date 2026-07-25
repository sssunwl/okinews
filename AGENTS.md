# OKIPLAYGROUND 公開網站規則

本資料夾是 OKIPLAYGROUND 對外旅遊資訊平台的網站與資料爬蟲。網站的第一任務是幫旅客快速回答「今天在沖繩可以做什麼」，第二任務才是導流到 Facebook 社群。

## 品牌與內容

- 對外品牌一律寫作 `OKIPLAYGROUND`，中文副名為「沖繩遊樂園」。
- 使用繁體中文，語氣像住在沖繩的朋友：直接、具體、有溫度，不堆砌旅遊形容詞。
- 不使用「沖繩藍」或沒有根據的最高級表述。
- 活動日期、地點與安全資訊必須有來源；爬取內容只顯示原始來源連結，不擅自補寫未驗證資訊。
- 品牌視覺與內容架構以 `../SonaSNS-Platform/brands/OKIPLAYGROUND/BRAND_DNA.md` 為準。

## 網站實作

- `site_template.html` 是頁面唯一模板；`okinawa_events_crawler.py` 只負責資料與模板合成。
- `docs/index.html` 是 GitHub Pages 產物，每次修改模板後必須重新生成並以桌面、手機尺寸檢查。
- 所有從外部網站爬取的文字在插入 DOM 前必須 escape；外部 URL 只接受 `http:` 或 `https:`。
- 互動功能必須可用鍵盤操作，動畫需尊重 `prefers-reduced-motion`。
- 不加入需要 API key 的前端功能，憑證只使用 GitHub Secrets。
