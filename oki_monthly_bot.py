import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin
import time

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
BASE_URL = "https://visitokinawajapan.com/zh-hant/discover/events/"
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def send_telegram(chat_id, message):
    url = f"{TELEGRAM_API}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        resp = requests.post(url, data=data)
        resp.raise_for_status()
    except Exception as e:
        print(f"Telegram 發送失敗：{e}")

def get_monthly_events(month: int):
    resp = requests.get(BASE_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    events_section = soup.find("h2", string="搜尋熱門活動")
    if not events_section:
        return []

    events = []
    for dt in events_section.find_all_next("dt"):
        name = dt.text.strip()
        e_content = dt.find_next_sibling("div", class_="e-content")
        if not e_content:
            continue
        date_text = e_content.text.strip()
        if not date_text:
            continue

        try:
            start_str = date_text.split("-")[0].strip()
            start_date = datetime.strptime(start_str, "%Y/%m/%d")
        except Exception:
            continue

        if start_date.month != month:
            continue

        link_tag = dt.find_parent("a")
        if link_tag and link_tag.get("href"):
            link = urljoin(BASE_URL, link_tag["href"])
        else:
            link = BASE_URL

        events.append((date_text, name, link))
    return events

def handle_message(message):
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    if not text.isdigit():
        send_telegram(chat_id, "請輸入月份數字 (1~12)")
        return

    month = int(text)
    if not 1 <= month <= 12:
        send_telegram(chat_id, "月份輸入錯誤，請輸入 1~12")
        return

    events = get_monthly_events(month)
    if not events:
        send_telegram(chat_id, f"{month}月沒有新的活動。")
        return

    message_text = f"{month}月活動：\n"
    for date_text, name, link in events:
        message_text += f"{date_text}\n[{name}]({link})\n"

    send_telegram(chat_id, message_text)

def main():
    offset = None
    while True:
        url = f"{TELEGRAM_API}/getUpdates"
        params = {"timeout": 100, "offset": offset}
        try:
            resp = requests.get(url, params=params, timeout=120)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"取得訊息失敗：{e}")
            time.sleep(5)
            continue

        for result in data.get("result", []):
            offset = result["update_id"] + 1
            handle_message(result.get("message", {}))

        time.sleep(1)

if __name__ == "__main__":
    if not TELEGRAM_TOKEN:
        print("請先設定 TELEGRAM_TOKEN 環境變數")
    else:
        main()
