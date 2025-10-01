import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# GitHub Actions 環境變數
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not TELEGRAM_TOKEN or not CHAT_ID:
    raise ValueError("請在 GitHub Actions 設定 TELEGRAM_TOKEN 和 CHAT_ID Secret")

headers = {"User-Agent": "Mozilla/5.0"}

# 網站設定
sites = [
    {
        "name": "Visit Okinawa Japan",
        "url": "https://visitokinawajapan.com/zh-hant/discover/events/",
    },
    {
        "name": "Okinawa Story",
        "url": "https://www.okinawastory.jp/event/",
    },
    {
        "name": "Naha Navi",
        "url": "https://www.naha-navi.or.jp/event/",
    },
]

def fetch_visitokinawa():
    url = "https://visitokinawajapan.com/zh-hant/discover/events/"
    try:
        res = requests.get(url, headers=headers)
        res.raise_for_status()
    except Exception as e:
        print(f"Visit Okinawa Japan 抓取失敗: {e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    events = []

    # Visit Okinawa 網站沒有統一日期欄位，所以不抓日期
    for item in soup.select("a"):  # 可以依需求調整 selector
        text = item.get_text(strip=True)
        if text:
            events.append({"name": text, "date": None})
    return events

def fetch_okinawastory():
    url = "https://www.okinawastory.jp/event/"
    try:
        res = requests.get(url, headers=headers)
        res.raise_for_status()
    except Exception as e:
        print(f"Okinawa Story 抓取失敗: {e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    events = []
    for item in soup.select("p.os-c-list-cmn__lead"):
        text = item.get_text(strip=True)
        if not text:
            continue
        # 解析日期和活動名稱
        parts = text.split(" ")
        date_str = parts[0].replace("〜", "-").replace("(", "").replace(")", "")
        try:
            start_date = datetime.strptime(date_str.split("-")[0], "%Y年%m月%d日")
        except:
            start_date = None
        if start_date and start_date < datetime.today():
            continue  # 過期活動不列
        events.append({"name": " ".join(parts[1:]) or text, "date": text})
    return events

def fetch_nahanavi():
    url = "https://www.naha-navi.or.jp/event/"
    try:
        res = requests.get(url, headers=headers)
        res.raise_for_status()
    except Exception as e:
        print(f"Naha Navi 抓取失敗: {e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    events = []
    for item in soup.select("div.entry-card__contents span.icon-schedule span"):
        date_text = item.get_text(strip=True)
        if not date_text:
            continue
        # 取得活動日期
        try:
            start_date = datetime.strptime(date_text.split("-")[0], "%Y/%m/%d")
        except:
            start_date = None
        if start_date and start_date < datetime.today():
            continue  # 過期活動不列
        # 活動名稱在前一個 span 或 div？
        parent = item.find_parent("div", class_="entry-card__contents")
        if parent:
            name_tag = parent.find("h3")  # 假設 h3 裡有活動名稱
            name = name_tag.get_text(strip=True) if name_tag else "活動名稱未提供"
            events.append({"name": name, "date": date_text})
    return events

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        res = requests.post(url, data=payload, timeout=10)
        res.raise_for_status()
        print("Telegram 發送成功")
    except Exception as e:
        print(f"Telegram 發送失敗: {e}")

def main():
    all_events = []

    print("開始抓取 Visit Okinawa Japan")
    vk_events = fetch_visitokinawa()
    print(f"Visit Okinawa Japan：抓到 {len(vk_events)} 個活動")
    all_events.append(("Visit Okinawa Japan", "https://visitokinawajapan.com/zh-hant/discover/events/", vk_events))

    print("開始抓取 Okinawa Story")
    os_events = fetch_okinawastory()
    print(f"Okinawa Story：抓到 {len(os_events)} 個活動")
    all_events.append(("Okinawa Story", "https://www.okinawastory.jp/event/", os_events))

    print("開始抓取 Naha Navi")
    nn_events = fetch_nahanavi()
    print(f"Naha Navi：抓到 {len(nn_events)} 個活動")
    all_events.append(("Naha Navi", "https://www.naha-navi.or.jp/event/", nn_events))

    # 組合訊息
    msg_parts = []
    for site_name, site_url, events in all_events:
        if events:
            msg_parts.append(f"來自 {site_name} 的最新活動 ({site_url})：")
            for e in events:
                if e["date"]:
                    msg_parts.append(f"{e['date']}\n{e['name']}")
                else:
                    msg_parts.append(f"{e['name']}")
            msg_parts.append("")  # 空行分隔
        else:
            msg_parts.append(f"{site_name}：今天沒有新的活動 ({site_url})\n")

    full_msg = "\n".join(msg_parts)
    send_telegram(full_msg)

if __name__ == "__main__":
    main()
