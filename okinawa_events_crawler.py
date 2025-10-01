import requests
from bs4 import BeautifulSoup
import os

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

websites = [
    {"name": "Visit Okinawa", "url": "https://www.visitokinawa.jp/events", "selector": "h2.event-title"},
    {"name": "Okinawa Story", "url": "https://www.okinawastory.jp/", "selector": "div.event-title a"},
    {"name": "Naha Navi", "url": "https://www.naha-navi.or.jp/?utm_source=chatgpt.com", "selector": "div.news-list a"},
]

all_events = []

for site in websites:
    try:
        resp = requests.get(site["url"], headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()  # 網頁回傳不是 200 會丟錯
        soup = BeautifulSoup(resp.text, "lxml")
        events = soup.select(site["selector"])
        titles = [e.get_text(strip=True) for e in events]

        print(f"Fetched {site['name']}: {len(titles)} events found")
        if titles:
            all_events.append(f"來自 {site['name']} 的最新活動：")
            all_events.extend(titles)
        else:
            all_events.append(f"{site['name']}：沒有更新")
    except Exception as e:
        all_events.append(f"{site['name']}：抓取失敗，原因：{e}")
        print(f"Error fetching {site['name']}: {e}")

# 組 Telegram 訊息
message = "\n".join(all_events) if all_events else "目前沒有新的活動資訊。"

# 發送 Telegram
try:
    url_telegram = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url_telegram, data={"chat_id": CHAT_ID, "text": message})
    resp.raise_for_status()
    print("Telegram message sent successfully")
except Exception as e:
    print(f"Telegram 發送失敗：{e}")
