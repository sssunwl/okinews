#!/usr/bin/env python3
"""沖繩新聞・日本大事：每日抓取 + 用 OpenAI 整理成繁中摘要，寫進 docs/news.json。

來源：
- 沖縄タイムス RSS（沖繩在地新聞）
- NHK 主要ニュース RSS（日本大事）
- 気象庁 警報・注意報 JSON（沖繩四個地方：本島／大東／宮古／八重山）

全自動發佈，沒有人審這道關，所以機器關卡在這支程式裡：缺必要欄位、抓取失敗、
翻譯失敗的項目一律跳過，不讓半成品上線；整批失敗時保留上一版 docs/news.json，
不產生空白頁。只做短摘要＋原文連結，不做全文翻譯轉載。
"""

import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

from build import build_site

ROOT = Path(__file__).parent
NEWS_FILE = ROOT / "docs" / "news.json"
EVENTS_FILE = ROOT / "docs" / "events.json"
WEATHER_FILE = ROOT / "docs" / "weather.json"

JST = timezone(timedelta(hours=9))
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

LOOKBACK_HOURS = 30       # 抓過去幾小時內發布的新聞
KEEP_DAYS = 4             # 網站上保留幾天份
MAX_OKINAWATIMES = 15     # 沖繩在地新聞單日最多整理幾則
MAX_NHK = 8               # 日本大事單日最多整理幾則
SUMMARY_MAX_CHARS = 120

CATEGORIES = ["生活", "交通", "天氣警報", "觀光", "全國"]

OKINAWATIMES_RSS = "https://www.okinawatimes.co.jp/list/feed/rss"
NHK_RSS = "https://www3.nhk.or.jp/rss/news/cat0.xml"
JMA_AREAS = {
    "471000": "沖繩本島地方",
    "472000": "大東島地方",
    "473000": "宮古島地方",
    "474000": "八重山地方",
}

REPORT = {"generated": "", "fetched": 0, "summarized": 0, "skipped": []}


def skip(what, why):
    REPORT["skipped"].append({"item": what, "reason": why})
    print("⏭️  跳過 {}：{}".format(what, why))


# ── OpenAI client（讀不到 key 就整支程式優雅退化：只重建網頁不抓新聞）──────

def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        cred_path = Path.home() / ".config" / "openai" / "credentials.json"
        if cred_path.exists():
            try:
                api_key = json.loads(cred_path.read_text())["api_key"]
            except (ValueError, KeyError, OSError):
                api_key = None
    if not api_key:
        return None
    try:
        from openai import OpenAI
    except ImportError:
        print("⚠️  沒裝 openai 套件（pip install openai），略過新聞摘要")
        return None
    return OpenAI(api_key=api_key)


# ── RSS 抓取 ──────────────────────────────────────────────────────────

def fetch_rss(url, limit):
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
    except requests.RequestException as error:
        skip(url, "RSS 抓取失敗（{}）".format(error))
        return []

    try:
        root = ET.fromstring(res.content)
    except ET.ParseError as error:
        skip(url, "RSS 格式解析失敗（{}）".format(error))
        return []

    cutoff = datetime.now(JST) - timedelta(hours=LOOKBACK_HOURS)
    items = []
    for node in root.iter("item"):
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        description = re.sub(r"<[^>]+>", "", node.findtext("description") or "").strip()
        pub_date_raw = node.findtext("pubDate")
        if not title or not link.startswith(("http://", "https://")) or not pub_date_raw:
            continue
        try:
            pub_dt = parsedate_to_datetime(pub_date_raw)
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=JST)
        except (TypeError, ValueError):
            continue
        if pub_dt < cutoff:
            continue
        items.append({
            "title": title,
            "url": link,
            "description": description,
            "date": pub_dt.astimezone(JST).strftime("%Y-%m-%d"),
        })
        if len(items) >= limit:
            break
    return items


# ── 気象庁 警報・注意報 ────────────────────────────────────────────────

def fetch_jma_alerts():
    today = datetime.now(JST).strftime("%Y-%m-%d")
    alerts = []
    for code, area_name in JMA_AREAS.items():
        url = "https://www.jma.go.jp/bosai/warning/data/warning/{}.json".format(code)
        try:
            res = requests.get(url, headers=HEADERS, timeout=15)
            res.raise_for_status()
            data = res.json()
        except (requests.RequestException, ValueError) as error:
            skip("JMA {}".format(area_name), "抓取失敗（{}）".format(error))
            continue
        headline = (data.get("headlineText") or "").strip()
        if not headline:
            continue
        alerts.append({
            "title": "{}氣象警報・注意報".format(area_name),
            "description": headline,
            "date": today,
            "url": "https://www.jma.go.jp/bosai/warning/#area_type=class20s&area_code={}&lang=ja".format(code),
            "area": area_name,
        })
    return alerts


# ── OpenAI 摘要 ───────────────────────────────────────────────────────

SYSTEM_PROMPT = """你是幫沖繩旅遊網站 OkinawaSundays 做新聞整理的編輯。收到一則日文新聞的標題與內容，請整理成繁體中文，規則：

1. title_zh：翻譯成繁體中文標題，簡潔具體，不超過 40 字。
2. summary_zh：用 2-3 句繁體中文摘要，只摘要原文寫到的事實，不要杜撰數字、地名或細節，總長度不超過 {max_chars} 字。
3. category：從這五個裡面選一個最貼切的：{categories}。
4. alert：如果這則新聞會影響到來沖繩旅遊的旅客（例如颱風、航班或船班停飛、道路封閉、活動取消或異動、生效中的重大天氣警報），設為 true；否則 false。如果內容是「警報／注意報已解除」這種恢復正常的通知，alert 設為 false。

只回傳這個 JSON，不要加其他文字、不要加 markdown code fence：
{{"title_zh": "...", "summary_zh": "...", "category": "...", "alert": true}}""".format(
    max_chars=SUMMARY_MAX_CHARS, categories="、".join(CATEGORIES)
)


def summarize(client, source, title_ja, description_ja):
    user_content = "標題：{}\n內容：{}".format(title_ja, description_ja[:1000])
    try:
        response = client.chat.completions.create(
            model="gpt-5.4-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )
        raw = response.choices[0].message.content.strip()
    except Exception as error:  # noqa: BLE001 — 第三方 API 各種例外都當成跳過處理
        skip("{}：{}".format(source, title_ja[:30]), "OpenAI 呼叫失敗（{}）".format(error))
        return None

    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(raw)
    except ValueError:
        skip("{}：{}".format(source, title_ja[:30]), "回傳不是合法 JSON")
        return None

    title_zh = str(data.get("title_zh", "")).strip()
    summary_zh = str(data.get("summary_zh", "")).strip()
    category = str(data.get("category", "")).strip()
    alert = bool(data.get("alert", False))

    if not title_zh or not summary_zh:
        skip("{}：{}".format(source, title_ja[:30]), "標題或摘要是空的")
        return None
    if category not in CATEGORIES:
        category = "生活" if source != "NHK" else "全國"
    if len(summary_zh) > SUMMARY_MAX_CHARS:
        summary_zh = summary_zh[:SUMMARY_MAX_CHARS].rstrip() + "…"

    return {"title": title_zh, "summary": summary_zh, "category": category, "alert": alert}


# ── 主流程 ────────────────────────────────────────────────────────────

def load_existing():
    if not NEWS_FILE.exists():
        return []
    try:
        return json.loads(NEWS_FILE.read_text(encoding="utf-8"))
    except ValueError:
        return []


def prune(items):
    cutoff_date = (datetime.now(JST) - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    return [item for item in items if item.get("date", "") >= cutoff_date]


def valid_item(item):
    if not item.get("title") or not item.get("summary"):
        return False
    if not item.get("source") or not item.get("date"):
        return False
    url = item.get("url", "")
    if not url.startswith(("http://", "https://")):
        return False
    if len(item.get("summary", "")) > SUMMARY_MAX_CHARS + 5:
        return False
    return True


def main():
    now = datetime.now(JST)
    REPORT["generated"] = now.strftime("%Y-%m-%d %H:%M")

    existing = load_existing()
    existing_by_url = {item["url"]: item for item in existing if item.get("url")}
    # JMA 警報是「現況」，每次都重新產生，避免舊警報卡著不退場
    existing_by_url = {
        url: item for url, item in existing_by_url.items() if item.get("source") != "氣象庁警報"
    }

    client = get_openai_client()
    if client is None:
        print("⚠️  沒有可用的 OpenAI key，只重建網頁、不更新新聞內容")
        build_site()
        return

    raw_items = []
    for item in fetch_rss(OKINAWATIMES_RSS, MAX_OKINAWATIMES):
        raw_items.append(("沖縄タイムス", item))
    for item in fetch_rss(NHK_RSS, MAX_NHK):
        raw_items.append(("NHK", item))
    for item in fetch_jma_alerts():
        raw_items.append(("氣象庁警報", item))

    REPORT["fetched"] = len(raw_items)

    results = []
    for source, item in raw_items:
        if item["url"] in existing_by_url:
            results.append(existing_by_url[item["url"]])
            continue
        summarized = summarize(client, source, item["title"], item["description"])
        if not summarized:
            continue
        results.append({
            "date": item["date"],
            "source": source,
            "title": summarized["title"],
            "summary": summarized["summary"],
            "category": summarized["category"],
            "url": item["url"],
            "alert": summarized["alert"],
        })
        REPORT["summarized"] += 1

    merged_by_url = {item["url"]: item for item in existing_by_url.values()}
    for item in results:
        merged_by_url[item["url"]] = item

    final = [item for item in merged_by_url.values() if valid_item(item)]
    final = prune(final)
    final.sort(key=lambda item: (item.get("date", ""), item.get("alert", False)), reverse=True)

    if not final and existing:
        print("⚠️  這次抓不到任何有效新聞，保留上一版")
        final = existing

    NEWS_FILE.parent.mkdir(parents=True, exist_ok=True)
    NEWS_FILE.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")

    events = json.loads(EVENTS_FILE.read_text(encoding="utf-8")) if EVENTS_FILE.exists() else []
    weather = json.loads(WEATHER_FILE.read_text(encoding="utf-8")) if WEATHER_FILE.exists() else []
    build_site(events=events, weather=weather, updated=now.strftime("%Y-%m-%d %H:%M"))

    (ROOT / "docs" / "news-report.json").write_text(
        json.dumps(REPORT, ensure_ascii=False, indent=2), encoding="utf-8")

    print("📰 新聞更新完成：抓到 {} 則、新摘要 {} 則、上線 {} 則".format(
        REPORT["fetched"], REPORT["summarized"], len(final)))
    if REPORT["skipped"]:
        print("⏭️  跳過 {} 筆（詳見 docs/news-report.json）".format(len(REPORT["skipped"])))


if __name__ == "__main__":
    main()
