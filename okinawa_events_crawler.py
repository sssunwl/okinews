import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# Telegram 設定
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# 網站資訊
SITES = [
    {
        "name": "Visit Okinawa Japan",
        "url": "https://visitokinawajapan.com/zh-hant/discover/events/"
    },
    {
        "name": "Okinawa Story",
        "url": "https://www.okinawastory.jp/event/"
    },
    {
        "name": "Naha Navi",
        "url": "https://www.naha-navi.or.jp/event/"
    }
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def fetch_visitokinawa():
    URL = "https://visitokinawajapan.com/zh-hant/discover/events/"
    try:
        resp = requests.get(URL, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"抓取 Visit Okinawa Japan 發生錯誤：{e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    events = []

    # 取活動列表
    for card in soup.select(".card__body"):
        name_tag = card.select_one(".card__title")
        date_tag = card.select_one(".card__meta-date")
        if name_tag:
            name = name_tag.get_text(strip=True)
            date = date_tag.get_text(strip=True) if date_tag else ""
            
            # 過濾過期
            if date:
                try:
                    start_date = datetime.strptime(date.split("-")[0].strip(), "%Y/%m/%d")
                    if start_date < datetime.now():
                        continue
                except:
                    pass

            events.append({"name": name, "date": date})
    return events

def fetch_okinawastory():
    URL = "https://www.okinawastory.jp/event/"
    try:
        resp = requests.get(URL, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"抓取 Okinawa Story 發生錯誤：{e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    events = []

    for card in soup.select(".os-c-list-cmn-tile-event"):
        name_tag = card.select_one(".os-c-list-cmn__title")
        date_tag = card.select_one(".os-c-list-cmn__lead")
        if name_tag:
            name = name_tag.get_text(strip=True)
            date = date_tag.get_text(strip=True) if date_tag else ""
            
            # 過濾過期
            if date:
                try:
                    start_date = datetime.strptime(date.split("〜")[0].strip().replace("年","/").replace("月","/").replace("日",""), "%Y/%m/%d")
                    if start_date < datetime.now():
                        continue
                except:
                    pass

            events.append({"name": name, "date": date})
    return events

def fetch_nahanavi():
    URL = "https://www.naha-navi.or.jp/event/"
    try:
        resp = requests.get(URL, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"抓取 Naha Navi 發生錯誤：{e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    events = []

    for card in soup.select(".entry-card__contents"):
        name_tag = card.select_one(".entry-card__title")
        date_tag = card.select_one(".icon-schedule span")
        if name_tag:
            name = name_tag.get_text(strip=True)
            date = date_tag.get_text(strip=True) if date_tag else ""

            # 過濾過期
            if date:
                try:
                    start_date = datetime.strptime(date.split("-")[0].strip(), "%Y/%m/%d")
                    if start_date < datetime.now():
                        continue
                except:
                    pass

            events.append({"name": name, "date": date})
    return events

def send_telegram(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram Token 或 Chat ID 未設定")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, data={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"})
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Telegram 發送失敗：{e}")

def main():
    site_fetch_map = {
        "Visit Okinawa Japan": fetch_visitokinawa,
        "Okinawa Story": fetch_okinawastory,
        "Naha Navi": fetch_nahanavi
    }

    messages = []
    for site in SITES:
        name = site["name"]
        url = site["url"]
        print(f"開始抓取 {name} → {url}")
        events = site_fetch_map[name]()
        print(f"{name}：抓到 {len(events)} 個活動")

        if events:
            msg = f"來自 {name} 的最新活動 ({url})：\n"
            for event in events:
                if event["date"]:
                    msg += f"- {event['date']}\n  {event['name']}\n"
                else:
                    msg += f"- {event['name']}\n"
            messages.append(msg)
        else:
            messages.append(f"{name}：今天沒有新的活動 ({url})")

    # 合併訊息
    final_message = "\n\n".join(messages)
    send_telegram(final_message)

if __name__ == "__main__":
    main()
