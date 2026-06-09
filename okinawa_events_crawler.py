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
    seen_urls = set()

    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
    except Exception as e:
        print(f"⚠️ visitokinawa 連線失敗：{e}")
        return events

    soup = BeautifulSoup(res.text, "lxml")

    for a in soup.find_all("a", href=True):
        link = a["href"]
        # 只保留真實 URL，跳過 javascript: 和其他非 http 連結
        if link.startswith("javascript:") or not link.startswith(("http", "/")):
            continue

        dt_tag = a.find("dt")
        date_div = a.find("div", class_="e-content")
        if not dt_tag or not date_div:
            continue

        name = dt_tag.get_text(strip=True)
        date_text = date_div.get_text(strip=True)

        if link.startswith("/"):
            link = "https://visitokinawajapan.com" + link

        if link in seen_urls:
            continue
        seen_urls.add(link)

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
    """okinawastory.jp — 日文來源，爬全部頁數（~216 筆活動）"""
    base = "https://www.okinawastory.jp"
    events = []
    now = datetime.now()
    seen_hrefs = set()

    for page in range(1, 20):
        url = f"{base}/event?month=all&page={page}" if page > 1 else f"{base}/event?month=all"
        try:
            res = requests.get(url, headers=HEADERS, timeout=15)
            res.raise_for_status()
        except Exception as e:
            print(f"⚠️ okinawastory page {page} 失敗：{e}")
            break

        soup = BeautifulSoup(res.text, "lxml")

        title_links = soup.find_all("a", class_="os-c-list-cmn__title-link")
        if not title_links:
            break  # 已到末頁

        for a in title_links:
            href = a.get("href", "")
            if not re.match(r'^/event/\d+', href):
                continue
            if href in seen_hrefs:
                continue
            seen_hrefs.add(href)

            name_ja = a.get_text(strip=True)
            if not name_ja:
                continue

            # 日期在父層 div 的兄弟 p 標籤
            container = a.find_parent("div", class_="os-c-list-cmn__inner")
            date_tag = container.find("p", class_="os-c-list-cmn__lead") if container else None
            date_text = date_tag.get_text(strip=True) if date_tag else ""

            # 過濾條件：只保留近期或即將開始的活動（最多往前 7 天，往後 90 天）
            if not date_text:
                continue
            if "〜" in date_text:
                parts = date_text.split("〜")
                start_dt = parse_date_jp(parts[0].strip())
                end_dt = parse_date_jp(parts[-1].strip())
                if end_dt and end_dt < now:
                    continue
                if start_dt and start_dt < now - timedelta(days=7):
                    continue
                if start_dt and start_dt > now + timedelta(days=90):
                    continue
            else:
                single_dt = parse_date_jp(date_text)
                if single_dt and (single_dt < now - timedelta(days=1) or single_dt > now + timedelta(days=90)):
                    continue

            events.append({
                "name": name_ja,
                "name_zh": "",
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
    return f"{flag} [{title}]({e['url']})\n"


def send_telegram(text):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ 未設定 TELEGRAM_TOKEN 或 CHAT_ID")
        return

    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    # 逐行切割，確保每條訊息不超過 4096 字元且不截斷 Markdown 連結
    lines = text.split("\n")
    chunk = ""
    for line in lines:
        candidate = chunk + line + "\n"
        if len(candidate) > 4096:
            if chunk.strip():
                _post_telegram(api_url, chunk.strip())
            chunk = line + "\n"
        else:
            chunk = candidate
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
    is_manual = os.getenv("MANUAL_TRIGGER") == "1"

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

    # 週五 或 手動觸發：完整活動總覽
    if is_friday or is_manual:
        msg = f"📅 沖繩活動總覽（共 {len(all_events)} 個）\n\n"
        for e in all_events:
            msg += format_event(e)
        send_telegram(msg)

    # 清除 seen 中的 javascript: 殘留，只保留正常 URL
    clean_seen = {u for u in seen if u.startswith("http")}
    save_seen(clean_seen | {e["url"] for e in all_events})


if __name__ == "__main__":
    main()
