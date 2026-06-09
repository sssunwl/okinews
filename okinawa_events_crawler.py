import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
import json
import re

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SEEN_FILE = "seen_events.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f).get("seen", []))
    return set()


def save_seen(seen_urls):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"seen": sorted(seen_urls), "updated": datetime.now().isoformat()},
            f, ensure_ascii=False, indent=2
        )


def translate_ja_zh(text):
    """Japanese → Traditional Chinese via unofficial Google Translate"""
    try:
        resp = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "ja", "tl": "zh-TW", "dt": "t", "q": text},
            headers=HEADERS,
            timeout=10
        )
        return resp.json()[0][0][0]
    except Exception:
        return ""


def parse_date_zh(text):
    try:
        return datetime.strptime(text.strip(), "%Y/%m/%d")
    except Exception:
        return None


def parse_date_jp(text):
    text = re.sub(r'[（(][^）)]+[）)]', '', text).strip()
    try:
        return datetime.strptime(text, "%Y年%m月%d日")
    except Exception:
        return None


def get_visitokinawa_events():
    """visitokinawajapan.com — 繁體中文來源"""
    url = "https://visitokinawajapan.com/zh-hant/discover/events/"
    events = []
    now = datetime.now()
    upper = now + timedelta(days=90)

    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
    except Exception as e:
        print(f"⚠️ visitokinawa 連線失敗：{e}")
        return events

    soup = BeautifulSoup(res.text, "lxml")

    for a in soup.find_all("a", href=True):
        dt_tag = a.find("dt")
        date_div = a.find("div", class_="e-content")
        if not dt_tag or not date_div:
            continue

        name = dt_tag.get_text(strip=True)
        date_text = date_div.get_text(strip=True)
        link = a["href"]
        if link.startswith("/"):
            link = "https://visitokinawajapan.com" + link

        parts = date_text.split("-")
        if len(parts) < 2:
            continue

        start_dt = parse_date_zh(parts[0])
        end_dt = parse_date_zh(parts[-1])

        if start_dt and end_dt and end_dt >= now and start_dt <= upper:
            events.append({
                "name": name,
                "name_zh": name,
                "date": date_text,
                "url": link,
                "source": "visitokinawa"
            })

    print(f"✅ visitokinawa: {len(events)} 筆")
    return events


def get_okinawastory_events():
    """okinawastory.jp — 日文來源，共 200+ 筆活動"""
    base = "https://www.okinawastory.jp"
    url = f"{base}/event/?month=all"
    events = []
    now = datetime.now()
    seen_hrefs = set()

    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
    except Exception as e:
        print(f"⚠️ okinawastory 連線失敗：{e}")
        return events

    soup = BeautifulSoup(res.text, "lxml")

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not re.match(r'^/event/\d+', href):
            continue
        if href in seen_hrefs:
            continue
        seen_hrefs.add(href)

        # Title
        name_tag = a.find(["h3", "h2", "h4", "dt", "strong"])
        name_ja = name_tag.get_text(strip=True) if name_tag else ""
        if not name_ja:
            texts = [t.strip() for t in a.stripped_strings]
            name_ja = texts[0] if texts else ""
        if not name_ja:
            continue

        # Date
        date_text = ""
        for string in a.stripped_strings:
            if re.search(r'\d{4}年\d{1,2}月\d{1,2}日', string):
                date_text = string
                break

        # Filter out past events
        if date_text and "〜" in date_text:
            end_part = date_text.split("〜")[-1].strip()
            end_dt = parse_date_jp(end_part)
            if end_dt and end_dt < now:
                continue

        events.append({
            "name": name_ja,
            "name_zh": "",  # filled in add_translations()
            "date": date_text,
            "url": base + href,
            "source": "okinawastory"
        })

    print(f"✅ okinawastory: {len(events)} 筆（翻譯前）")
    return events


def add_translations(events, seen_urls):
    """只翻譯新活動，節省請求次數"""
    to_translate = [
        e for e in events
        if e["source"] == "okinawastory" and e["url"] not in seen_urls
    ]
    print(f"🔤 翻譯 {len(to_translate)} 個新活動...")
    for e in to_translate:
        e["name_zh"] = translate_ja_zh(e["name"])


def merge(lists):
    seen_urls = set()
    merged = []
    for events in lists:
        for e in events:
            if e["url"] not in seen_urls:
                seen_urls.add(e["url"])
                merged.append(e)
    return merged


def format_event(e):
    if e["source"] == "okinawastory":
        zh = e.get("name_zh", "")
        title = f"{zh}（{e['name']}）" if zh else e["name"]
        flag = "🇯🇵"
    else:
        title = e["name"]
        flag = "🌏"

    date = f"\n📆 {e['date']}" if e.get("date") else ""
    return f"{flag} [{title}]({e['url']}){date}\n\n"


def send_telegram(text):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ 未設定 TELEGRAM_TOKEN 或 CHAT_ID")
        return

    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    # Split at event boundaries to avoid cutting Markdown links
    lines = text.split("\n\n")
    chunk = ""
    for line in lines:
        if len(chunk) + len(line) + 2 > 4096:
            _post_telegram(api_url, chunk.strip())
            chunk = line + "\n\n"
        else:
            chunk += line + "\n\n"
    if chunk.strip():
        _post_telegram(api_url, chunk.strip())


def _post_telegram(api_url, text):
    try:
        resp = requests.post(
            api_url,
            data={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=15
        )
        resp.raise_for_status()
        print("Telegram 發送成功 ✅")
    except Exception as e:
        print(f"Telegram 發送失敗：{e}")


def main():
    is_friday = datetime.now().weekday() == 4

    all_events = merge([
        get_visitokinawa_events(),
        get_okinawastory_events(),
    ])
    print(f"📦 合計（去重後）：{len(all_events)} 筆")

    seen = load_seen()
    new_events = [e for e in all_events if e["url"] not in seen]
    print(f"🆕 新活動：{len(new_events)} 筆")

    # 只翻譯新活動
    add_translations(all_events, seen)

    # 每日：只推送新增活動
    if new_events:
        msg = f"🆕 沖繩新活動（{len(new_events)} 個）\n\n"
        for e in new_events:
            msg += format_event(e)
        send_telegram(msg)
    else:
        print("今日無新活動，略過通知。")

    # 週五：完整活動總覽
    if is_friday:
        msg = f"📅 沖繩活動週報（共 {len(all_events)} 個）\n\n"
        for e in all_events:
            msg += format_event(e)
        send_telegram(msg)

    save_seen(seen | {e["url"] for e in all_events})


if __name__ == "__main__":
    main()
