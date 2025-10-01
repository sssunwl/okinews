#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# 取得 GitHub Actions Secret
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

if not TELEGRAM_TOKEN or not CHAT_ID:
    raise ValueError("請在 GitHub Actions 設定 TELEGRAM_TOKEN 和 CHAT_ID Secret")

# Telegram 發送訊息
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    r = requests.post(url, data=payload)
    r.raise_for_status()
    return r.json()

# 判斷活動是否在今天之後
def is_future_event(start_date, end_date=None):
    today = datetime.today()
    if end_date is None:
        return start_date >= today
    return end_date >= today

# Visit Okinawa Japan
def fetch_visitokinawa():
    url = "https://visitokinawajapan.com/zh-hant/discover/events/"
    res = requests.get(url)
    soup = BeautifulSoup(res.text, "html.parser")
    events = []
    # 只抓 dt 標籤作活動名稱，日期網站沒提供
    for dt in soup.select("dt"):
        name = dt.get_text(strip=True)
        if name:
            events.append((None, name))
    return url, events

# Okinawa Story
def fetch_okinawastory():
    url = "https://www.okinawastory.jp/event/"
    res = requests.get(url)
    soup = BeautifulSoup(res.text, "html.parser")
    events = []
    for p in soup.select("p.os-c-list-cmn__lead.os-c-list-cmn-tile-event-lead"):
        text = p.get_text(strip=True)
        if text:
            # 將日子解析成 start_date, end_date
            try:
                date_range = text.replace("年","-").replace("月","-").replace("日","").replace("(","").replace(")","").split("〜")
                start_date = datetime.strptime(date_range[0].strip(), "%Y-%m-%d")
                end_date = datetime.strptime(date_range[1].strip(), "%Y-%m-%d") if len(date_range) > 1 else start_date
                if is_future_event(start_date, end_date):
                    name_tag = p.find_previous_sibling("a")
                    name = name_tag.get_text(strip=True) if name_tag else "未知活動"
                    events.append((f"{start_date.strftime('%Y/%m/%d')} - {end_date.strftime('%Y/%m/%d')}", name))
            except:
                continue
    return url, events

# Naha Navi
def fetch_nahanavi():
    url = "https://www.naha-navi.or.jp/event/"
    res = requests.get(url)
    soup = BeautifulSoup(res.text, "html.parser")
    events = []
    for entry in soup.select("div.entry-card__contents"):
        name_tag = entry.select_one("h2.entry-card__title")
        date_tag = entry.select_one("span.icon-schedule span")
        if name_tag and date_tag:
            try:
                dates = date_tag.get_text(strip=True).split(" - ")
                start_date = datetime.strptime(dates[0], "%Y/%m/%d")
                end_date = datetime.strptime(dates[1], "%Y/%m/%d") if len(dates) > 1 else start_date
                if is_future_event(start_date, end_date):
                    name = name_tag.get_text(strip=True)
                    events.append((f"{start_date.strftime('%Y/%m/%d')} - {end_date.strftime('%Y/%m/%d')}", name))
            except:
                continue
    return url, events

# 組合訊息
def main():
    messages = []

    for fetcher, title in [(fetch_visitokinawa, "Visit Okinawa Japan"),
                           (fetch_okinawastory, "Okinawa Story"),
                           (fetch_nahanavi, "Naha Navi")]:
        site_url, events = fetcher()
        if events:
            msg = f"來自 {title} 的最新活動 ({site_url})：\n"
            for date, name in events:
                if date:
                    msg += f"{date}\n{name}\n"
                else:
                    msg += f"{name}\n"
            messages.append(msg)
        else:
            messages.append(f"{title}：今天沒有新的活動 ({site_url})\n")

    full_msg = "\n".join(messages)
    if full_msg:
        send_telegram(full_msg)
        print("Telegram 發送成功")
    else:
        print("沒有新活動可發送")

if __name__ == "__main__":
    main()
