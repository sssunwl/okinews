import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin

# 讀取 Telegram Token 與 Chat ID
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

BASE_URL = "https://visitokinawajapan.com/zh-hant/discover/events/"

def send_telegram(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram Token 或 Chat ID 未設定")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        resp = requests.post(url, data=data)
        resp.raise_for_status()
        print("Telegram 發送成功 ✅")
    except Exception as e:
        print(f"Telegram 發送失敗：{e}")

def get_monthly_events(month: int):
    resp = requests.get(BASE_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    # 最新即時活動的區塊
    events_section = soup.find("h2", string="搜尋熱門活動")
    if not events_section:
        return []

    events = []
    # 取得所有 dt 與其後面的 .e-content
    for dt in events_section.find_all_next("dt"):
        name = dt.text.strip()
        # 活動日子在下一個 .e-content
        e_content = dt.find_next_sibling("div", class_="e-content")
        if not e_content:
            continue
        date_text = e_content.text.strip()
        if not date_text:
            continue

        # 檢查活動是否屬於指定月份
        try:
            start_str = date_text.split("-")[0].strip()
            start_date = datetime.strptime(start_str, "%Y/%m/%d")
        except Exception:
            continue
        if start_date.month != month:
            continue

        # 超連結
        link_tag = dt.find_parent("a")
        if link_tag and link_tag.get("href"):
            link = urljoin(BASE_URL, link_tag["href"])
        else:
            link = BASE_URL

        events.append((date_text, name, link))
    return events

def main():
    # 這裡可改成從 Telegram 接收月份數字
    # 目前示範用輸入
    month_input = input("請輸入月份 (1~12)：")
    try:
        month = int(month_input)
        if not 1 <= month <= 12:
            raise ValueError
    except ValueError:
        print("月份輸入錯誤")
        return

    events = get_monthly_events(month)
    if not events:
        send_telegram(f"{month}月沒有新的活動。")
        return

    message = f"{month}月活動：\n"
    for date_text, name, link in events:
        message += f"{date_text}\n[{name}]({link})\n"

    send_telegram(message)

if __name__ == "__main__":
    main()
