import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
import json
import re
from collections import defaultdict

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SEEN_FILE = "seen_events.json"
EVENTS_FILE = "docs/events.json"
HTML_FILE = "docs/index.html"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
WEEKDAYS = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]


# ── 日期解析 ──────────────────────────────────────────────────────────

def parse_iso(text):
    try:
        return datetime.strptime(text.strip(), "%Y/%m/%d")
    except Exception:
        return None


def parse_jp(text):
    text = re.sub(r'[（(][^）)]+[）)]', '', text).strip()
    try:
        return datetime.strptime(text, "%Y年%m月%d日")
    except Exception:
        return None


def to_iso(dt):
    return dt.strftime("%Y-%m-%d") if dt else ""


# ── 翻譯 ─────────────────────────────────────────────────────────────

def translate_ja_zh(text):
    try:
        resp = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "ja", "tl": "zh-TW", "dt": "t", "q": text},
            headers=HEADERS, timeout=10
        )
        return resp.json()[0][0][0]
    except Exception:
        return ""


def load_translation_cache():
    if os.path.exists(EVENTS_FILE):
        with open(EVENTS_FILE, "r", encoding="utf-8") as f:
            return {e["url"]: e.get("name_zh", "") for e in json.load(f)}
    return {}


# ── 爬蟲 ─────────────────────────────────────────────────────────────

def get_visitokinawa_events():
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
        start_dt = parse_iso(parts[0])
        end_dt = parse_iso(parts[-1])
        if not start_dt or not end_dt:
            continue
        if end_dt < now or start_dt > upper:
            continue

        events.append({
            "name": name, "name_zh": name,
            "date_start": to_iso(start_dt), "date_end": to_iso(end_dt),
            "url": link, "source": "visitokinawa"
        })

    print(f"✅ visitokinawa: {len(events)} 筆")
    return events


def get_okinawastory_events():
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
            break

        for a in title_links:
            href = a.get("href", "")
            if not re.match(r'^/event/\d+', href) or href in seen_hrefs:
                continue
            seen_hrefs.add(href)

            name_ja = a.get_text(strip=True)
            if not name_ja:
                continue

            container = a.find_parent("div", class_="os-c-list-cmn__inner")
            date_tag = container.find("p", class_="os-c-list-cmn__lead") if container else None
            date_text = date_tag.get_text(strip=True) if date_tag else ""

            if not date_text or "〜" not in date_text:
                continue
            parts = date_text.split("〜")
            start_dt = parse_jp(parts[0].strip())
            end_dt = parse_jp(parts[-1].strip())
            if not start_dt or not end_dt:
                continue
            if end_dt < now:
                continue
            if start_dt < now - timedelta(days=7):
                continue
            if start_dt > now + timedelta(days=90):
                continue

            events.append({
                "name": name_ja, "name_zh": "",
                "date_start": to_iso(start_dt), "date_end": to_iso(end_dt),
                "url": base + href, "source": "okinawastory"
            })

    print(f"✅ okinawastory: {len(events)} 筆")
    return events


def merge(lists):
    seen_urls = set()
    merged = []
    for events in lists:
        for e in events:
            if e["url"] not in seen_urls:
                seen_urls.add(e["url"])
                merged.append(e)
    merged.sort(key=lambda x: x["date_start"])
    return merged


def apply_translations(events, cache):
    to_translate = [e for e in events if e["source"] == "okinawastory" and not e["name_zh"]]
    # 先套用快取
    for e in to_translate:
        if cache.get(e["url"]):
            e["name_zh"] = cache[e["url"]]
    # 再翻譯真正新的
    truly_new = [e for e in to_translate if not e["name_zh"]]
    print(f"🔤 翻譯 {len(truly_new)} 個新活動...")
    for e in truly_new:
        e["name_zh"] = translate_ja_zh(e["name"])


# ── 網頁生成 ──────────────────────────────────────────────────────────

def generate_html(events, updated_str):
    by_month = defaultdict(list)
    for e in events:
        if e["date_start"]:
            dt = datetime.strptime(e["date_start"], "%Y-%m-%d")
            by_month[(dt.year, dt.month)].append(e)

    tabs_html = ""
    sections_html = ""
    for (year, month) in sorted(by_month.keys()):
        mid = f"m{year}{month:02d}"
        tabs_html += f'<a href="#{mid}" class="tab">{year}/{month}</a>\n'

        rows = ""
        for e in by_month[(year, month)]:
            s = datetime.strptime(e["date_start"], "%Y-%m-%d")
            en = datetime.strptime(e["date_end"], "%Y-%m-%d")
            wd = WEEKDAYS[s.weekday()]
            date_str = f"{s.month}/{s.day}({wd})"
            if e["date_start"] != e["date_end"]:
                date_str += f"～{en.month}/{en.day}"

            zh = e.get("name_zh", "")
            if e["source"] == "okinawastory":
                flag = "🇯🇵"
                display = f'{zh}<span class="ja">（{e["name"]}）</span>' if zh else e["name"]
            else:
                flag = "🌏"
                display = e["name"]

            rows += f'''<div class="ev">
              <span class="dt">{date_str}</span>
              <span class="fl">{flag}</span>
              <a href="{e['url']}" target="_blank">{display}</a>
            </div>'''

        n = len(by_month[(year, month)])
        sections_html += f'''<section id="{mid}">
          <h2>{year}年{month}月 <small>（{n} 個活動）</small></h2>
          <div class="list">{rows}</div>
        </section>'''

    return f'''<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>沖繩活動年曆</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f0f4f8;color:#222}}
header{{background:#0d5c8a;color:#fff;padding:18px 20px}}
header h1{{font-size:1.4rem}}
header p{{font-size:.8rem;opacity:.75;margin-top:4px}}
nav{{display:flex;gap:6px;padding:12px 16px;overflow-x:auto;background:#fff;border-bottom:1px solid #ddd;position:sticky;top:0;z-index:10}}
.tab{{padding:5px 12px;border-radius:16px;background:#eee;text-decoration:none;color:#555;font-size:.85rem;white-space:nowrap}}
.tab:hover{{background:#0d5c8a;color:#fff}}
section{{margin:14px;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
section h2{{background:#0d5c8a;color:#fff;padding:10px 16px;font-size:.95rem;font-weight:600}}
section h2 small{{font-weight:400;opacity:.8}}
.list{{padding:0 4px}}
.ev{{display:flex;align-items:flex-start;gap:8px;padding:10px 12px;border-bottom:1px solid #f0f0f0}}
.ev:last-child{{border-bottom:none}}
.dt{{min-width:110px;font-size:.78rem;color:#666;padding-top:2px;flex-shrink:0}}
.fl{{font-size:.9rem;flex-shrink:0}}
.ev a{{color:#0d5c8a;text-decoration:none;font-size:.88rem;line-height:1.4}}
.ev a:hover{{text-decoration:underline}}
.ja{{color:#999;font-size:.78rem}}
footer{{text-align:center;padding:20px;color:#aaa;font-size:.78rem}}
@media(max-width:400px){{.dt{{min-width:80px}}}}
</style>
</head>
<body>
<header>
  <h1>🏝️ 沖繩活動年曆</h1>
  <p>來源：Visit Okinawa Japan ＋ おきなわ物語 ｜ 更新：{updated_str} ｜ 共 {len(events)} 個活動</p>
</header>
<nav>{tabs_html}</nav>
{sections_html}
<footer>每日自動更新</footer>
</body>
</html>'''


# ── Telegram ──────────────────────────────────────────────────────────

def fmt_tg(e):
    dt = datetime.strptime(e["date_start"], "%Y-%m-%d")
    wd = WEEKDAYS[dt.weekday()]
    end = datetime.strptime(e["date_end"], "%Y-%m-%d")
    date_str = f"{dt.month}/{dt.day}({wd})" + (f"～{end.month}/{end.day}" if e["date_start"] != e["date_end"] else "")

    zh = e.get("name_zh", "")
    if e["source"] == "okinawastory":
        title = f"{zh}（{e['name']}）" if zh else e["name"]
        flag = "🇯🇵"
    else:
        title = e["name"]
        flag = "🌏"

    return f"📅 {date_str} {flag} [{title}]({e['url']})\n"


def send_telegram(text):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ 未設定 TELEGRAM_TOKEN 或 CHAT_ID")
        return
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    lines = text.split("\n")
    chunk = ""
    for line in lines:
        candidate = chunk + line + "\n"
        if len(candidate) > 4096:
            if chunk.strip():
                _post(api_url, chunk.strip())
            chunk = line + "\n"
        else:
            chunk = candidate
    if chunk.strip():
        _post(api_url, chunk.strip())


def _post(api_url, text):
    try:
        resp = requests.post(api_url,
            data={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=15)
        resp.raise_for_status()
        print("Telegram 發送成功 ✅")
    except Exception as e:
        print(f"Telegram 發送失敗：{e}")


# ── seen_events ───────────────────────────────────────────────────────

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f).get("seen", []))
    return set()


def save_seen(urls):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump({"seen": sorted(u for u in urls if u.startswith("http")),
                   "updated": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)


# ── 主程式 ────────────────────────────────────────────────────────────

def main():
    is_manual = os.getenv("MANUAL_TRIGGER") == "1"
    now = datetime.now()

    all_events = merge([get_visitokinawa_events(), get_okinawastory_events()])
    print(f"📦 合計：{len(all_events)} 筆")

    seen = load_seen()
    new_events = [e for e in all_events if e["url"] not in seen]
    print(f"🆕 新活動：{len(new_events)} 筆")

    cache = load_translation_cache()
    apply_translations(all_events, cache)

    # 生成網頁
    os.makedirs("docs", exist_ok=True)
    with open(EVENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_events, f, ensure_ascii=False, indent=2)
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(generate_html(all_events, now.strftime("%Y-%m-%d %H:%M")))
    print(f"📄 網頁已更新：{len(all_events)} 個活動")

    # Telegram：近 7 天即將開始的活動
    upcoming = [e for e in all_events
                if e["date_start"] and
                now <= datetime.strptime(e["date_start"], "%Y-%m-%d") <= now + timedelta(days=7)]

    if upcoming:
        msg = f"📅 近 7 天沖繩活動（{len(upcoming)} 個）\n\n"
        for e in upcoming:
            msg += fmt_tg(e)
        send_telegram(msg)

    if new_events:
        msg = f"🆕 新上架活動（{len(new_events)} 個）\n\n"
        for e in new_events:
            msg += fmt_tg(e)
        send_telegram(msg)

    if is_manual and not upcoming and not new_events:
        send_telegram("✅ 近期無新活動，年曆網頁已更新。")

    save_seen(seen | {e["url"] for e in all_events})


if __name__ == "__main__":
    main()
