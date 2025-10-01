#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

if not TELEGRAM_TOKEN or not CHAT_ID:
    raise ValueError("請先在 GitHub Secrets 設定 TELEGRAM_TOKEN 與 CHAT_ID")

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        res = requests.post(url, data=payload)
        res.raise_for_status()
    except Exception as e:
        print(f"Telegram 發送失敗：{e}")

def fetch_visitokinawa():
    url = "https://visitokinawajapan.com/zh-hant/discover/events/"
    events = []
    try:
        res = requests.get(url)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        items = soup.select(".c-event-card__title")
        for item in items:
            name = item.get_text(strip=True)
            events.append({"name": name})
    except Exception as e:
        print(f"Visit Okinawa Japan 擷取失敗：{e}")
    return events, url

def fetch_okinawastory():
    url = "https://www.okinawastory.jp/event/"
    events = []
    try:
        res = requests.get(url)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        items = soup.select(".os-c-list-cmn__title-link")
        dates = soup.select(".os-c-list-cmn__lead")
        for i, item in enumerate(items):
            name = item.get_text(strip=True)
            date_str = dates[i].get_text(strip=True) if i < len(dates) else ""
            # 解析日期範圍
            try:
                date_str = date_str.replace("〜", "-").replace("年","-").replace("月","-").replace("日","")
                start_str, end_str = date_str.split("-")[:2]
                start_date = datetime.strptime(start_str.strip(), "%Y-%m-%d") if "-" in start_str else datetime.strptime(start_str.strip(), "%Y/%m/%d")
                end_date = datetime.strptime(end_str.strip(), "%Y-%m-%d") if "-" in end_str else datetime.strptime(end_str.strip(), "%Y/%m/%d")
                if end_date < datetime.now():
                    continue  # 過期活動跳過
                events.append({"name": name, "date": f"{start_date.date()} - {end_date.date()}"})
            except:
                events.append({"name": name})
    except Exception as e:
        print(f"Okinawa Story 擷取失敗：{e}")
    return events, url

def fetch_nahanavi():
    url = "https://www.naha-navi.or.jp/event/"
    events = []
    try:
        res = requests.get(url)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        items = soup.select(".entry-card__title")
        dates = soup.select(".icon-schedule span")
        for i, item in enumerate(items):
            name = item.get_text(strip=True)
            date_str = dates[i].get_text(strip=True) if i < len(dates) else ""
            try:
                start_str, end_str = date_str.split("-")
                start_date = datetime.strptime(start_str.strip(), "%Y/%m/%d")
                end_date = datetime.strptime(end_str.strip(), "%Y/%m/%d")
                if end_date < datetime.now():
                    continue  # 過期活動跳過
                events.append({"name": name, "date": f"{start_date.date()} - {end_date.date()}"})
            except:
                events.append({"name": name})
    except Exception as e:
        print(f"Naha Navi 擷取失敗：{e}")
    return events, url

def main():
    try:
        all_sources = [
            fetch_visitokinawa(),
            fetch_okinawastory(),
            fetch_nahanavi()
        ]

        for events, url in all_sources:
            if not events:
                message = f"今天沒有新的活動 ({url})"
            else:
                message = f"來自 {url} 的最新活動：\n"
                for event in events:
                    if "date" in event:
                        message += f"{event['date']}\n{event['name']}\n"
                    else:
                        message += f"{event['name']}\n"
            send_telegram(message)

    except Exception as e:
        print(f"程式執行失敗: {e}")

if __name__ == "__main__":
    main()
