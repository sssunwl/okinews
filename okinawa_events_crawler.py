import requests
from bs4 import BeautifulSoup
import os

# Telegram Bot 設定
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

# 網站設定
websites = [
    {
        "name": "Visit Okinawa",
        "url": "https://www.visitokinawa.jp/events",
        "selector": "h2.event-title",
    },
    {
        "name": "Okinawa Story",
        "url": "https://www.okinawastory.jp/",
        "selector": "div.event-title a",
    },
    {
        "name": "Naha Navi",
        "url": "https://www.naha-navi.or.jp/?utm_source=chatgpt.com",
        "selector": "div.news-list a",
    }
]

# 儲存所有活動資訊
all_events = []

# 爬取每個網站的活動資訊
for site in websites:
    try:
        resp = requests.get(site["url"], headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "lxml")
        events = soup.select(si
