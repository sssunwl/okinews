import requests
from bs4 import BeautifulSoup
import os

# 網站 URL
URL = "https://www.visitokinawa.jp/events"  # 這裡可換成真實活動頁面
HEADERS = {"User-Agent": "Mozilla/5.0"}

# 取得網頁內容
resp = requests.get(URL, headers=HEADERS)
soup = BeautifulSoup(resp.text, "lxml")

# 抓取活動標題
events = soup.select("h2.event-title")  # 根據網站實際 HTML 調整
event_list = [e.text.strip() for e in events]

# 發送到 Telegram
if event_list:
    message = "最新沖繩活動：\n" + "\n".join(event_list)
    TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
    CHAT_ID = os.environ["CHAT_ID"]
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": message})
