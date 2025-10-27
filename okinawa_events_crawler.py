import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os

# Telegram 設定（從環境變數讀）
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# 目標網站
URL = "https://visitokinawajapan.com/zh-hant/discover/events/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def get_visit_okinawa_events():
    print("開始抓取 Visit Okinawa Japan 最新即時活動...")
    events = []

    try:
        res = requests.get(URL, headers=HEADERS, timeout=15)
        res.raise_for_status()
    except Exception as e:
        print("⚠️ 無法連線至網站：", e)
        return events

    soup = BeautifulSoup(res.text, "html.parser")

    # 找到 "最新即時活動" 區塊
    section = soup.find("h2", string="最新即時活動")
    if not section:
        print("⚠️ 找不到『最新即時活動』區塊。")
        return events

    container = section.find_next("div")  # 下一個 div 內包含活動卡片
    if not container:
        print("⚠️ 找不到活動列表。")
        return events

    # 找出每個活動區塊
    for item in container.find_all("a", href=True):
        name_tag = item.find("dt")
        date_tag = item.find("div", class_="e-content")

        if not name_tag:
            continue

        name = name_tag.get_text(strip=True)
        date = date_tag.get_text(strip=True) if date_tag else ""
        link = item["href"]
        if not link.startswith("http"):
            link = "https://visitokinawajapan.com" + link

        # 過濾已結束的活動
        if date and "-" in date:
            try:
                end_date = date.split("-")[-1].strip()
                end_dt = datetime.strptime(end_date, "%Y/%m/%d")
                if end_dt < datetime.now():
                    continue
            except Exception:
                pass

        events.append({"name": name, "date": date, "url": link})

    print(f"✅ 共找到 {len(events)} 個未來活動")
    return events

def send_to_telegram(events):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ 未設定 TELEGRAM_TOKEN 或 CHAT_ID，略過發送。")
        return

    if not events:
        message = "本週沒有新的活動。"
    else:
        message = "📅 沖繩最新即時活動\n\n"
        for e in events:
            message += f"{e['date']}\n[{e['name']}]({e['url']})\n"

    send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        resp = requests.post(send_url, data=data)
        resp.raise_for_status()
        print("Telegram 發送成功 ✅")
    except Exception as e:
        print("Telegram 發送失敗：", e)

if __name__ == "__main__":
    events = get_visit_okinawa_events()
    send_to_telegram(events)
