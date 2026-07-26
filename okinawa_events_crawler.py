import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
import json
import re
import time

from build import build_site

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SEEN_FILE = "seen_events.json"
EVENTS_FILE = "docs/events.json"
WEATHER_FILE = "docs/weather.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
WEEKDAYS = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
WEEKDAYS_SHORT = "一二三四五六日"
OKINAWA_LAT, OKINAWA_LON = 26.2124, 127.6809

# ── 今天是… 完整年曆（12個月）──────────────────────────────────────
# (月, 日, 中文名, emoji, 分類, 推薦星數, 沖繩/日本視角的小介紹)
TODAY_IS_DATA = [
    # ── 1月 ──
    (1,  1, "元旦",          "🎍", "傳統", 5, "沖繩人在首里城前迎接第一道日出，新年的喜慶從南島海邊開始"),
    (1,  7, "七草粥",        "🌿", "傳統", 4, "春の七草煮成粥，祈求一整年無病息災，開啟清淡健康的新年"),
    (1, 17, "飯糰日",        "🍙", "生活", 2, "沖繩口味飯糰：豬肉蛋SPAM是早餐招牌，比7-11還道地"),
    (1, 20, "大寒",          "❄️", "節氣", 4, "一年最寒冷的節氣，沖繩卻依然溫暖，珊瑚礁在冬日清澈如鏡"),
    # ── 2月 ──
    (2,  3, "節分",          "👹", "傳統", 5, "撒豆驅鬼迎春的年度儀式，沖繩各神社也熱鬧非凡，喊出「鬼は外！福は内！」"),
    (2,  4, "立春",          "🌸", "節氣", 4, "春季正式開始，緋寒櫻早已在沖繩盛開，是全日本最早能賞到的櫻花"),
    (2, 14, "情人節",        "💝", "生活", 3, "日本傳統由女生送巧克力，沖繩海景餐廳也常推出期間限定餐點"),
    (2, 22, "貓の日",        "🐈", "生活", 3, "2-22音似「喵喵喵」，散步時常會遇到在街角曬太陽的島貓"),
    # ── 3月 ──
    (3,  3, "雛祭り",        "🎎", "傳統", 4, "女兒節，沖繩版雛人偶穿上琉球傳統服飾，紅型染布色彩比本土版更鮮艷"),
    (3, 21, "春分",          "🌸", "節氣", 5, "晝夜等長，水溫逐漸回升；安排浮潛前仍要確認當日海況"),
    (3, 31, "珊瑚の日",      "🪸", "海洋", 5, "認識沖繩珊瑚礁的紀念日，也提醒旅客留意白化與海洋保育"),
    # ── 4月 ──
    (4,  5, "清明（シーミー）","⛩️","沖繩", 5, "沖繩獨有的掃墓祭祖習俗，全家聚集在大型龜甲墓前野餐，充滿人情溫度"),
    (4, 20, "穀雨",          "🌧️", "節氣", 4, "春雨滋潤大地，沖繩迎來梅雨前最後的晴朗天氣，出海好時機"),
    (4, 29, "昭和の日",      "🏯", "歷史", 3, "黃金週的開始，首里城祭典與傳統藝能表演在此期間熱鬧上演"),
    # ── 5月 ──
    (5, 18, "國際博物館日",  "🎨", "文化", 3, "走進沖繩縣立博物館，追溯琉球王國五百年歷史，珍稀文物不設門票限制"),
    (5, 20, "森林日",        "🌳", "自然", 4, "山原（ヤンバル）世界自然遺產孕育山原秧雞等沖繩獨有珍稀物種，嚴禁採集"),
    (5, 21, "小滿",          "🌾", "節氣", 5, "萬物初成熟的節氣，沖繩苦瓜與島野菜進入最鮮甜的產季"),
    (5, 22, "國際生物多樣性日","🪸","海洋", 5, "從珊瑚礁到山原森林，沖繩有多種島嶼生態值得慢慢認識"),
    (5, 25, "主婦休息日",    "☕", "生活", 2, "找間咖啡店坐一個下午，讓旅行也留一段什麼都不趕的時間"),
    (5, 26, "風呂日",        "♨️", "文化", 2, "5-26諧音「お風呂」，不少飯店設有展望浴場，適合排在行程收尾"),
    (5, 29, "幸福日",        "😊", "生活", 3, "5-29諧音「こうふく」，沖繩的「なんくるないさ」哲學就是隨遇而安的幸福"),
    (5, 30, "零垃圾日",      "♻️", "永續", 5, "5-30音似「ゴミゼロ」，沖繩海灘淨灘全年不停歇，守護這片珊瑚海"),
    # ── 6月 ──
    (6,  1, "泡盛之日",      "🍶", "沖繩", 5, "泡盛是琉球王國傳承500年的蒸餾酒，古酒「クース」越陳越香，值得細細品味"),
    (6,  4, "蟲牙預防日",    "🦷", "文化", 2, "6-4諧音「虫歯」，日本的牙齒保健意識極高，記得回國前去看一次牙醫"),
    (6,  8, "世界海洋日",    "🌊", "海洋", 5, "沖繩蔚藍之海是地球的瑰寶，珊瑚礁生態系守護著無數海洋生命"),
    (6, 11, "國際玩樂日",    "🎮", "生活", 2, "浮潛、SUP、藍染手工藝，沖繩的「玩法」完全不需要電子設備"),
    (6, 15, "沖繩戰跡紀念",  "🕊️", "歷史", 4, "到糸滿的平和祈念公園，從沖繩戰役留下的記錄理解和平的重量"),
    (6, 21, "夏至",          "☀️", "節氣", 5, "全年白天較長的時節，傍晚可以把散步留給那霸港灣"),
    (6, 23, "慰靈之日",      "🕊️", "沖繩", 5, "沖繩縣特有的法定假日，紀念1945年沖繩戰役結束，全島為和平祈禱默哀"),
    (6, 26, "露天風呂日",    "♨️", "文化", 2, "露天溫泉與沖繩夜景的絕妙組合，在大自然懷抱中完全放鬆"),
    (6, 30, "夏越之祓",      "⛩️", "傳統", 5, "在神社鑽過茅之輪祓除上半年穢氣，為下半年的自己重新出發"),
    # ── 7月 ──
    (7,  1, "海開季",        "🏖️", "夏日", 5, "沖繩各海水浴場正式開放，一整個夏天的藍色冒險從這天拉開序幕"),
    (7,  7, "七夕",          "🎋", "傳統", 5, "牛郎織女一年一度相會，在沖繩海邊許願，無光害的星空特別璀璨"),
    (7, 10, "納豆日",        "🫘", "文化", 2, "7-10音似「なっとう」，沖繩人對這黏黏食物評價兩極，你是哪一邊？"),
    (7, 15, "海之日",        "🌊", "傳統", 5, "日本國定假日，沖繩以海洋文化節慶感謝大海的慷慨饋贈"),
    (7, 20, "漢堡日",        "🍔", "文化", 3, "美軍基地文化影響了沖繩飲食，島上有不少美式漢堡店值得比較"),
    (7, 22, "大暑",          "☀️", "節氣", 4, "一年最熱的節氣，沖繩海水溫度達到頂峰，是夏季珊瑚礁最豐盛的時期"),
    (7, 25, "刨冰日",        "🍧", "夏日", 5, "7-25諧音「こおり」，沖繩ぜんざい冰品是在地必吃，紅豆刨冰清甜無比"),
    # ── 8月 ──
    (8,  1, "水の日",        "💧", "自然", 3, "沖繩珊瑚礁是天然的水質守護者，關注海洋就是關注地球的用水未來"),
    (8, 11, "山の日",        "⛰️", "自然", 4, "日本國定假日，山原の森林是沖繩的翠綠心臟，世界自然遺產等你步道探索"),
    (8, 13, "お盆",          "🏮", "傳統", 5, "迎接祖先靈魂的盂蘭盆節，街區裡常能聽見エイサー太鼓聲"),
    (8, 23, "処暑",          "🌬️", "節氣", 4, "暑熱漸退，但沖繩的夏天還會延續一個多月，海水依然溫暖清澈"),
    # ── 9月 ──
    (9,  9, "重陽",          "🍶", "傳統", 4, "菊花節，古人以菊花酒延年益壽，沖繩的泡盛正傳承著這份長壽哲學"),
    (9, 20, "敬老の日",      "👴", "生活", 4, "沖繩是世界知名的長壽之島，秘訣是泡盛少量飲、苦瓜天天吃、心情不著急"),
    (9, 23, "秋分",          "🍂", "節氣", 4, "晝夜再次等長，沖繩秋天溫柔宜人，海水依然溫暖，旅遊旺季正式開始"),
    # ── 10月 ──
    (10,  1, "日本酒の日",   "🍶", "文化", 3, "新米上市的季節，沖繩有自己的泡盛與島燒酎文化，值得比較細品"),
    (10,  4, "世界動物の日", "🐢", "海洋", 4, "沖繩海龜保育計畫舉世聞名，玳瑁與綠蠵龜每年在此海灘產卵繁殖"),
    (10, 10, "銭湯の日",     "♨️", "文化", 3, "10-10音似「銭湯」，泡完溫泉仰望沖繩秋夜星空，是絕佳的放空體驗"),
    (10, 31, "萬聖節",       "🎃", "文化", 3, "國際通り萬聖節遊行是沖繩秋季新興慶典，各式造型扮裝吸引大批人潮"),
    # ── 11月 ──
    (11,  3, "文化の日",     "🎭", "文化", 4, "首里城一帶常有文化活動，能近距離認識琉球王朝的服飾與藝能"),
    (11, 11, "沖繩泡盛祭",   "🍶", "沖繩", 5, "多家酒造會在泡盛活動齊聚，適合一次認識不同產地與古酒"),
    (11, 15, "七五三",       "👘", "傳統", 3, "孩子的成長祭典，沖繩版七五三穿上琉球傳統服飾，色彩繽紛格外可愛"),
    (11, 23, "勤労感謝の日", "🙏", "傳統", 4, "感謝勞動節，沖繩農漁業文化底蘊深厚，島上每一件食物都是勞動的成果"),
    # ── 12月 ──
    (12,  1, "手紙の日",     "✉️", "文化", 3, "寄一張沖繩明信片給遠方的朋友，比任何禮物都更有旅行的溫度"),
    (12,  7, "大雪",         "❄️", "節氣", 3, "北國進入積雪時節，沖繩白天仍常在 20°C 左右，早晚記得加件外套"),
    (12, 22, "冬至",         "🍋", "節氣", 5, "冬至日照時間較短，適合把夜晚留給溫泉、街區散步或觀星"),
    (12, 31, "大晦日",       "🎋", "傳統", 5, "除夕夜倒數，首里城大晦日特別活動，以最具琉球風情的方式跨越新年"),
]



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
            return {e["url"]: e.get("name_zh", "") for e in json.load(f) if e.get("url")}
    return {}


# ── 天氣（Open-Meteo，免金鑰） ────────────────────────────────────────

def weather_icon(code):
    if code == 0:
        return "☀️"
    if code in (1, 2):
        return "🌤️"
    if code == 3:
        return "☁️"
    if code in (45, 48):
        return "🌫️"
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "🌧️"
    if code in (95, 96, 99):
        return "⛈️"
    return "🌈"


def uv_label(value):
    if value < 3:
        return "低"
    if value < 6:
        return "中等"
    if value < 8:
        return "高"
    if value < 11:
        return "很高"
    return "極高"


def get_weather():
    params = (
        f"latitude={OKINAWA_LAT}&longitude={OKINAWA_LON}&timezone=Asia%2FTokyo"
        "&forecast_days=7"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min,"
        "precipitation_probability_max,uv_index_max"
    )
    try:
        res = requests.get(f"https://api.open-meteo.com/v1/forecast?{params}",
                            headers=HEADERS, timeout=15)
        res.raise_for_status()
        daily = res.json()["daily"]
    except Exception as e:
        print(f"⚠️ 天氣預報失敗：{e}")
        return []

    days = []
    for i, iso in enumerate(daily["time"]):
        dt = datetime.strptime(iso, "%Y-%m-%d")
        code = int(daily["weather_code"][i])
        uv = daily["uv_index_max"][i]
        days.append({
            "date": iso,
            "weekday": WEEKDAYS_SHORT[dt.weekday()],
            "icon": weather_icon(code),
            "temp_max": round(daily["temperature_2m_max"][i]),
            "temp_min": round(daily["temperature_2m_min"][i]),
            "rain_chance": round(daily["precipitation_probability_max"][i]),
            "uv": round(uv, 1),
            "uv_label": uv_label(uv),
        })
    print(f"✅ 天氣預報：{len(days)} 天")
    return days


# ── 今天是… 生成（前1年～後2年） ─────────────────────────────────────

def get_today_is_events():
    events = []
    now = datetime.now()
    for year in range(now.year - 1, now.year + 2):
        for (month, day, zh_name, emoji, cat, stars, desc) in TODAY_IS_DATA:
            try:
                dt = datetime(year, month, day)
            except ValueError:
                continue
            events.append({
                "name":        f"今天是 {emoji} {zh_name}",
                "name_zh":     f"{emoji} {zh_name}",
                "date_start":  to_iso(dt),
                "date_end":    to_iso(dt),
                "url":         "",
                "source":      "today_is",
                "category":    cat,
                "stars":       stars,
                "description": desc,
            })
    return events


# ── 詳情頁補充：地點／費用／圖片／介紹 ──────────────────────────────

ENRICH_FIELDS = ("image", "location", "price", "description", "official_url")


def safe_official_url(url):
    """只接受 http/https 的官方網址，其他一律當作沒有。"""
    url = (url or "").strip()
    return url if url.startswith(("http://", "https://")) else ""


def enrich_visitokinawa(url):
    """從 visitokinawajapan.com 活動詳情頁擷取地點、費用、圖片、介紹與官方網站。"""
    out = {"image": "", "location": "", "price": "", "description": "", "official_url": ""}
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
    except Exception as e:
        print(f"⚠️ 詳情頁失敗 {url}：{e}")
        return out

    soup = BeautifulSoup(res.text, "lxml")

    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"):
        out["image"] = og_image["content"]

    og_desc = soup.find("meta", property="og:description")
    if og_desc and og_desc.get("content"):
        out["description"] = og_desc["content"].strip()

    place = soup.find(class_="e-place")
    if place:
        content = place.find(class_="e-content")
        out["location"] = (content or place).get_text(" ", strip=True)

    price = soup.find(class_="e-price")
    if price:
        content = price.find(class_="e-content")
        out["price"] = (content or price).get_text(" ", strip=True)

    www = soup.find(class_="e-www")
    if www:
        link = www.find("a", href=True)
        if link:
            out["official_url"] = safe_official_url(link["href"])

    return out


def enrich_okinawastory(url):
    """從 okinawastory.jp 活動詳情頁擷取地點、費用、圖片、介紹（日文轉繁中）與官方網站。"""
    out = {"image": "", "location": "", "price": "", "description": "", "official_url": ""}
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
    except Exception as e:
        print(f"⚠️ 詳情頁失敗 {url}：{e}")
        return out

    soup = BeautifulSoup(res.text, "lxml")

    gallery_img = soup.find(class_="p-detail-gallery__unit-img")
    if gallery_img:
        src = gallery_img.get("data-src") or gallery_img.get("src") or ""
        if src.startswith("http"):
            out["image"] = src

    facility = {}
    facility_links = {}
    fac_block = soup.find(class_="p-detail-facility")
    if fac_block:
        for li in fac_block.select(".p-detail-facility__list-unit"):
            label = li.find(class_="p-detail-facility__list-title")
            value = li.find(class_="p-detail-facility__list-inner")
            if not (label and value):
                continue
            # address rows carry a sibling "MAP" button inside the same block;
            # only the first text-bearing span/p is the actual address.
            pre = value.find(class_="p-detail-pre") or value
            label_text = label.get_text(strip=True)
            facility[label_text] = pre.get_text(" ", strip=True)
            link = pre.find("a", href=True)
            if link:
                facility_links[label_text] = link["href"]

    venue = facility.get("開催場所", "")
    address = facility.get("住所", "")
    area = facility.get("エリア", "")
    out["location"] = " ・ ".join(p for p in (venue or area, address) if p)
    price_ja = facility.get("料金", "")
    out["price"] = "免費" if price_ja in ("無料", "無料。") else price_ja
    out["official_url"] = safe_official_url(facility_links.get("ウェブサイト", ""))

    desc_block = soup.find(class_="p-detail-discription")
    desc_ja = desc_block.get_text(" ", strip=True) if desc_block else ""
    # okinawastory falls back to this generic caption when an organizer
    # hasn't written a real description — treat it as "no description".
    if desc_ja and "施設ルート" not in desc_ja:
        out["description"] = translate_ja_zh(desc_ja[:150])

    return out


def needs_enrichment(existing_event):
    if not existing_event:
        return True
    if not existing_event.get("image") and not existing_event.get("location"):
        return True
    # 補跑一次官方網站欄位：舊資料沒有這個 key，強制重新抓一次詳情頁
    return "official_url" not in existing_event


# ── 爬蟲 ─────────────────────────────────────────────────────────────

def get_visitokinawa_events(existing_by_url=None):
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
        end_dt   = parse_iso(parts[-1])
        if not start_dt or not end_dt:
            continue
        if end_dt < now or start_dt > upper:
            continue
        event = {
            "name": name, "name_zh": name,
            "date_start": to_iso(start_dt), "date_end": to_iso(end_dt),
            "url": link, "source": "visitokinawa",
            "category": "", "stars": 0,
            "description": "", "image": "", "location": "", "price": "", "official_url": "",
        }
        prior = (existing_by_url or {}).get(link)
        if not needs_enrichment(prior):
            for field in ENRICH_FIELDS:
                event[field] = prior.get(field, "")
        else:
            event.update(enrich_visitokinawa(link))
            time.sleep(0.3)
        events.append(event)

    print(f"✅ visitokinawa: {len(events)} 筆")
    return events


def get_okinawastory_events(existing_by_url=None, translate_cache=None):
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
            date_tag  = container.find("p", class_="os-c-list-cmn__lead") if container else None
            date_text = date_tag.get_text(strip=True) if date_tag else ""
            if not date_text or "〜" not in date_text:
                continue
            parts    = date_text.split("〜")
            start_dt = parse_jp(parts[0].strip())
            end_dt   = parse_jp(parts[-1].strip())
            if not start_dt or not end_dt:
                continue
            if end_dt < now:
                continue
            if start_dt < now - timedelta(days=7):
                continue
            if start_dt > now + timedelta(days=90):
                continue
            link = base + href
            event = {
                "name": name_ja, "name_zh": "",
                "date_start": to_iso(start_dt), "date_end": to_iso(end_dt),
                "url": link, "source": "okinawastory",
                "category": "", "stars": 0,
                "description": "", "image": "", "location": "", "price": "", "official_url": "",
            }
            prior = (existing_by_url or {}).get(link)
            if not needs_enrichment(prior):
                for field in ENRICH_FIELDS:
                    event[field] = prior.get(field, "")
            else:
                event.update(enrich_okinawastory(link))
                time.sleep(0.3)
            events.append(event)

    print(f"✅ okinawastory: {len(events)} 筆")
    return events


def merge(lists):
    seen_keys = set()
    merged = []
    for events in lists:
        for e in events:
            key = e["url"] if e["url"] else f"{e['source']}_{e['date_start']}_{e.get('name_zh','')}"
            if key not in seen_keys:
                seen_keys.add(key)
                merged.append(e)
    merged.sort(key=lambda x: x["date_start"])
    return merged


def apply_translations(events, cache):
    for e in events:
        if e["source"] == "okinawastory" and not e["name_zh"]:
            e["name_zh"] = cache.get(e["url"], "") or translate_ja_zh(e["name"])


# ── 網頁生成 ──────────────────────────────────────────────────────────
# 網頁由 build.py 負責組裝，這支程式只管把資料寫進 docs/*.json。


# ── Telegram ──────────────────────────────────────────────────────────

def fmt_tg(e):
    dt  = datetime.strptime(e["date_start"], "%Y-%m-%d")
    end = datetime.strptime(e["date_end"], "%Y-%m-%d") if e.get("date_end") else dt
    wd  = WEEKDAYS[dt.weekday()]
    date_str = f"{dt.month}/{dt.day}({wd})"
    if e["date_start"] != e.get("date_end", e["date_start"]):
        date_str += f"～{end.month}/{end.day}"
    zh = e.get("name_zh") or e["name"]
    if e.get("url"):
        return f"📅 {date_str} [{zh}]({e['url']})\n"
    return f"📅 {date_str} {zh}\n"


def send_telegram(text):
    try:  # 同時鏡射到 Discord #n-okinews(失敗不影響 TG)
        from _discord import notify_discord
        notify_discord(text)
    except Exception:
        pass
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
        print("Telegram ✅")
    except Exception as e:
        print(f"Telegram 失敗：{e}")


# ── seen_events ───────────────────────────────────────────────────────

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f).get("seen", []))
    return set()


def save_seen(urls):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"seen": sorted(u for u in urls if u and u.startswith("http")),
             "updated": datetime.now().isoformat()},
            f, ensure_ascii=False, indent=2
        )


# ── 主程式 ────────────────────────────────────────────────────────────

def main():
    is_manual = os.getenv("MANUAL_TRIGGER") == "1"
    now = datetime.now()

    if os.getenv("BUILD_ONLY") == "1":
        with open(EVENTS_FILE, "r", encoding="utf-8") as f:
            existing = json.load(f)
        events = merge([
            get_today_is_events(),
            [event for event in existing if event.get("source") != "today_is"],
        ])
        weather = []
        if os.path.exists(WEATHER_FILE):
            with open(WEATHER_FILE, "r", encoding="utf-8") as f:
                weather = json.load(f)
        with open(EVENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(events, f, ensure_ascii=False, indent=2)
        build_site(events=events, weather=weather, updated=now.strftime("%Y-%m-%d %H:%M"))
        print(f"📄 預覽網頁更新完成（{len(events)} 筆）")
        return

    existing_by_url = {}
    if os.path.exists(EVENTS_FILE):
        with open(EVENTS_FILE, "r", encoding="utf-8") as f:
            existing_by_url = {e["url"]: e for e in json.load(f) if e.get("url")}

    today_is   = get_today_is_events()
    scraped    = merge([
        get_visitokinawa_events(existing_by_url),
        get_okinawastory_events(existing_by_url),
    ])
    all_events = merge([today_is, scraped])
    print(f"📦 合計：{len(all_events)} 筆（今天是… {len(today_is)} 筆）")

    seen = load_seen()
    new_events = [e for e in scraped if e["url"] not in seen]
    print(f"🆕 新活動：{len(new_events)} 筆")

    cache = load_translation_cache()
    apply_translations(all_events, cache)

    weather = get_weather()

    os.makedirs("docs", exist_ok=True)
    with open(EVENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_events, f, ensure_ascii=False, indent=2)
    with open(WEATHER_FILE, "w", encoding="utf-8") as f:
        json.dump(weather, f, ensure_ascii=False, indent=2)
    build_site(events=all_events, weather=weather, updated=now.strftime("%Y-%m-%d %H:%M"))

    upcoming_ti = [e for e in today_is
                   if now <= datetime.strptime(e["date_start"], "%Y-%m-%d") <= now + timedelta(days=7)]
    upcoming_ev = [e for e in scraped
                   if e["date_start"] and
                   now <= datetime.strptime(e["date_start"], "%Y-%m-%d") <= now + timedelta(days=7)]

    if upcoming_ti:
        msg = f"🌟 近 7 天「今天是…」（{len(upcoming_ti)} 個）\n\n"
        for e in upcoming_ti:
            msg += fmt_tg(e)
        send_telegram(msg)

    if upcoming_ev:
        msg = f"📅 近 7 天沖繩活動（{len(upcoming_ev)} 個）\n\n"
        for e in upcoming_ev:
            msg += fmt_tg(e)
        send_telegram(msg)

    if new_events:
        msg = f"🆕 新上架活動（{len(new_events)} 個）\n\n"
        for e in new_events:
            msg += fmt_tg(e)
        send_telegram(msg)

    if is_manual and not upcoming_ti and not upcoming_ev and not new_events:
        send_telegram("✅ 近期無新資料，年曆已更新。")

    save_seen(seen | {e["url"] for e in scraped})


if __name__ == "__main__":
    main()
