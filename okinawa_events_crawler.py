import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import os
from dotenv import load_dotenv

# --- 載入環境變數 ---
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# --- Telegram 發送函式 ---
def send_telegram(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram TOKEN 或 CHAT_ID 未設定")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    for chunk in [message[i:i+3500] for i in range(0, len(message), 3500)]:
        res = requests.post(url, data={"chat_id": CHAT_ID, "text": chunk, "parse_mode": "Markdown"})
        if not res.ok:
            print("Telegram 發送失敗：", res.status_code, res.text)

# --- 日期解析 ---
def parse_date_naha(text):
    try:
        start, end = text.strip().split(" - ")
        start_dt = datetime.strptime(start, "%Y/%m/%d")
        end_dt = datetime.strptime(end, "%Y/%m/%d")
        return start_dt, end_dt
    except:
        return None, None

def parse_date_oki(text):
    match = re.findall(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if len(match) >= 2:
        start = datetime(int(match[0][0]), int(match[0][1]), int(match[0][2]))
        end = datetime(int(match[1][0]), int(match[1][1]), int(match[1][2]))
        return start, end
    return None, None

today = datetime.now()

# --- Okinawa Story ---
story_url = "https://www.okinawastory.jp/event/"
story_res = requests.get(story_url)
story_soup = BeautifulSoup(story_res.text, "html.parser")
story_events = []
for tile in story_soup.select("li.os-c-list-cmn-tile-event"):
    title_tag = tile.select_one("a.os-c-list-cmn__title-link")
    date_tag = tile.select_one("p.os-c-list-cmn__lead.os-c-list-cmn-tile-event-lead")
    if title_tag and date_tag:
        name = title_tag.get_text(strip=T
