import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
import json
import re

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SEEN_FILE = "seen_events.json"
EVENTS_FILE = "docs/events.json"
HTML_FILE = "docs/index.html"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
WEEKDAYS = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]

# ── HTML 模板（用 <<<PLACEHOLDER>>> 注入動態內容）────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>🏝️ 沖繩活動年曆</title>
<link href="https://fonts.googleapis.com/css2?family=Pacifico&display=swap" rel="stylesheet">
<style>
:root{--ocean:#0A4E6B;--coral:#F06543;--sand:#FFF8EE;--yellow:#FFD166;--sky:#5BB8D4;--dark:#2C1810;--white:#fff}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Noto Sans TC",sans-serif;background:var(--sand);color:var(--dark);min-height:100vh}

/* ── Header ── */
header{background:linear-gradient(150deg,#0A3D5C 0%,#0A6E9A 55%,#2AA0C8 100%);padding:36px 20px 0;position:relative;overflow:hidden}
.sun{position:absolute;top:18px;right:24px;width:64px;height:64px;background:radial-gradient(circle,#FFEC6E 40%,#FFD166 70%,rgba(255,209,102,0) 100%);border-radius:50%;animation:sunPulse 4s ease-in-out infinite;z-index:1}
.sun::before{content:'';position:absolute;inset:-12px;background:radial-gradient(circle,rgba(255,209,102,0.35) 40%,transparent 70%);border-radius:50%;animation:sunPulse 4s ease-in-out infinite reverse}
.header-inner{text-align:center;position:relative;z-index:2;padding-bottom:24px}
.header-inner h1{font-family:'Pacifico',cursive;font-size:2rem;color:var(--yellow);text-shadow:2px 3px 10px rgba(0,0,0,0.4);animation:float 4s ease-in-out infinite;letter-spacing:1px}
.header-inner p{color:rgba(255,255,255,0.8);font-size:.78rem;margin-top:6px}
.wave-wrap{height:52px;position:relative;overflow:hidden}
.wave-wrap svg{position:absolute;bottom:0;width:220%;animation:waveFlow 10s linear infinite}
.wave-wrap svg:nth-child(2){animation:waveFlow 16s linear infinite reverse;opacity:.45}

/* ── Calendar ── */
.cal-card{background:var(--white);margin:18px 14px 10px;border-radius:22px;overflow:hidden;box-shadow:0 6px 24px rgba(10,78,107,0.14)}
.cal-nav{display:flex;align-items:center;justify-content:space-between;padding:14px 18px;background:var(--ocean)}
.cal-nav h2{color:var(--yellow);font-family:'Pacifico',cursive;font-size:1.1rem;letter-spacing:.5px}
.cal-nav button{background:rgba(255,255,255,0.18);border:none;color:var(--white);width:34px;height:34px;border-radius:50%;cursor:pointer;font-size:1rem;transition:all .2s;display:flex;align-items:center;justify-content:center}
.cal-nav button:hover{background:var(--coral);transform:scale(1.1)}
.wdays{display:grid;grid-template-columns:repeat(7,1fr);background:#EEF6FA;border-bottom:1px solid #D8EDF5}
.wday{text-align:center;padding:8px 0;font-size:.72rem;font-weight:700;color:#666}
.wday:first-child{color:var(--coral)}
.wday:last-child{color:var(--sky)}
#cal-grid{display:grid;grid-template-columns:repeat(7,1fr);padding:8px 6px 12px;gap:2px}
.day{min-height:50px;padding:5px 3px;text-align:center;border-radius:10px;cursor:pointer;transition:all .2s;position:relative}
.day:hover{background:#F0F7FA;transform:scale(1.06)}
.day.other{opacity:.28;cursor:default}
.day.other:hover{transform:none;background:none}
.day.has .num{color:var(--ocean);font-weight:800}
.day.sel{background:var(--ocean) !important}
.day.sel .num{color:var(--white) !important}
.day.today .num{background:var(--coral);color:var(--white);border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;margin:0 auto}
.num{font-size:.82rem;line-height:1.9}
.dots{display:flex;justify-content:center;gap:2px;margin-top:1px}
.dot{width:5px;height:5px;border-radius:50%;background:var(--coral)}
.dot.jp{background:var(--sky)}

/* ── Events ── */
.ev-section{padding:0 14px 30px}
.ev-header{display:flex;align-items:center;gap:8px;padding:14px 2px 10px}
.ev-header strong{color:var(--ocean);font-size:1rem}
.ev-count{background:var(--coral);color:var(--white);border-radius:12px;padding:2px 10px;font-size:.75rem;font-weight:700}
.ev-card{background:var(--white);border-radius:14px;padding:14px 16px 12px;margin-bottom:10px;border-left:4px solid var(--coral);box-shadow:0 2px 10px rgba(0,0,0,0.06);transition:transform .22s,box-shadow .22s;animation:slideUp .35s ease both}
.ev-card.jp{border-left-color:var(--sky)}
.ev-card:hover{transform:translateY(-3px);box-shadow:0 8px 20px rgba(0,0,0,0.11)}
.ev-dtag{display:inline-block;background:linear-gradient(90deg,var(--ocean),var(--sky));color:var(--white);font-size:.7rem;padding:3px 10px;border-radius:10px;margin-bottom:8px;font-weight:600}
.ev-zh{font-size:1rem;font-weight:700;color:var(--dark);line-height:1.45;margin-bottom:5px}
.ev-ja{font-size:.76rem;color:#aaa}
.ev-ja a{color:var(--sky);text-decoration:none}
.ev-ja a:hover{text-decoration:underline;color:var(--ocean)}
.ev-link{font-size:.75rem}
.ev-link a{color:var(--coral);text-decoration:none;font-weight:600}
.ev-link a:hover{text-decoration:underline}
.empty{text-align:center;padding:36px 20px;color:#bbb;font-size:.9rem}

footer{text-align:center;padding:20px;font-size:.75rem;color:#bbb;border-top:1px solid #eee}

/* ── Animations ── */
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}
@keyframes sunPulse{0%,100%{transform:scale(1)}50%{transform:scale(1.12)}}
@keyframes waveFlow{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}
@keyframes slideUp{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:translateY(0)}}

@media(max-width:400px){.header-inner h1{font-size:1.5rem}.day{min-height:42px}}
</style>
</head>
<body>

<header>
  <div class="sun"></div>
  <div class="header-inner">
    <h1>Okinawa 活動年曆</h1>
    <p>🌊 Visit Okinawa Japan ＋ おきなわ物語 ｜ 更新：<<<UPDATED>>></p>
  </div>
  <div class="wave-wrap">
    <svg viewBox="0 0 1440 52" preserveAspectRatio="none">
      <path d="M0,26 C200,52 400,0 600,26 C800,52 1000,0 1200,26 C1320,40 1380,16 1440,26 L1440,52 L0,52 Z" fill="#FFF8EE"/>
    </svg>
    <svg viewBox="0 0 1440 52" preserveAspectRatio="none">
      <path d="M0,26 C240,0 480,52 720,26 C960,0 1200,52 1440,26 L1440,52 L0,52 Z" fill="rgba(255,248,238,0.5)"/>
    </svg>
  </div>
</header>

<div class="cal-card">
  <div class="cal-nav">
    <button id="prev">&#9664;</button>
    <h2 id="month-title"></h2>
    <button id="next">&#9654;</button>
  </div>
  <div class="wdays">
    <div class="wday">日</div><div class="wday">一</div><div class="wday">二</div>
    <div class="wday">三</div><div class="wday">四</div><div class="wday">五</div><div class="wday">六</div>
  </div>
  <div id="cal-grid"></div>
</div>

<div class="ev-section">
  <div class="ev-header">
    <strong id="ev-title">本月活動</strong>
    <span class="ev-count" id="ev-count">0 個</span>
  </div>
  <div id="ev-list"></div>
</div>

<footer>每日自動更新 · 共 <<<TOTAL>>> 個活動 · <<<UPDATED>>></footer>

<script>
const EVENTS = <<<EVENTS_JSON>>>;
const byDate = {};
EVENTS.forEach(e => {
  if (!byDate[e.date_start]) byDate[e.date_start] = [];
  byDate[e.date_start].push(e);
});

const WD = ['週日','週一','週二','週三','週四','週五','週六'];
const MN = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];

let cy, cm, sel = null;

function fmtDate(s) {
  if (!s) return '';
  const d = new Date(s + 'T00:00:00');
  return (d.getMonth()+1) + '/' + d.getDate() + '(' + WD[d.getDay()] + ')';
}

function renderCal() {
  document.getElementById('month-title').textContent = cy + '年' + MN[cm];
  const first = new Date(cy, cm, 1);
  const last = new Date(cy, cm+1, 0);
  const now = new Date();
  const dow = first.getDay();
  let html = '';

  // prev month padding
  const prevLast = new Date(cy, cm, 0).getDate();
  for (let i = dow-1; i >= 0; i--)
    html += '<div class="day other"><div class="num">' + (prevLast-i) + '</div></div>';

  // current month
  for (let d = 1; d <= last.getDate(); d++) {
    const ds = cy + '-' + String(cm+1).padStart(2,'0') + '-' + String(d).padStart(2,'0');
    const has = !!byDate[ds];
    const isToday = d===now.getDate() && cm===now.getMonth() && cy===now.getFullYear();
    const isSel = ds === sel;
    let cls = 'day' + (has?' has':'') + (isToday?' today':'') + (isSel?' sel':'');
    let dots = '';
    if (has) {
      byDate[ds].slice(0,3).forEach(e => {
        dots += '<div class="dot' + (e.source==='okinawastory'?' jp':'') + '"></div>';
      });
    }
    html += '<div class="' + cls + '" onclick="pick(\'' + ds + '\')">'
          + '<div class="num">' + d + '</div>'
          + '<div class="dots">' + dots + '</div></div>';
  }

  // next month padding
  const total = Math.ceil((dow + last.getDate()) / 7) * 7;
  for (let d = 1; d <= total - dow - last.getDate(); d++)
    html += '<div class="day other"><div class="num">' + d + '</div></div>';

  document.getElementById('cal-grid').innerHTML = html;
}

function renderEvents() {
  const list = document.getElementById('ev-list');
  const prefix = cy + '-' + String(cm+1).padStart(2,'0');
  const events = sel
    ? (byDate[sel] || [])
    : EVENTS.filter(e => e.date_start && e.date_start.startsWith(prefix));

  document.getElementById('ev-title').textContent = sel ? fmtDate(sel) : cy + '年' + MN[cm];
  document.getElementById('ev-count').textContent = events.length + ' 個活動';

  if (!events.length) {
    list.innerHTML = '<div class="empty">🌊 這天沒有活動</div>';
    return;
  }

  list.innerHTML = events.map((e, i) => {
    const zh = e.name_zh || e.name;
    const ja = e.name;
    const isJp = e.source === 'okinawastory';
    const end = e.date_end && e.date_end !== e.date_start ? '～' + fmtDate(e.date_end) : '';
    const dtag = fmtDate(e.date_start) + end;
    const jaLine = (isJp && zh !== ja)
      ? '<div class="ev-ja"><a href="' + e.url + '" target="_blank">' + ja + '</a></div>'
      : '<div class="ev-link"><a href="' + e.url + '" target="_blank">🔗 活動詳情</a></div>';
    return '<div class="ev-card' + (isJp?' jp':'') + '" style="animation-delay:' + (i*0.04) + 's">'
      + '<div class="ev-dtag">' + dtag + '</div>'
      + '<div class="ev-zh">' + zh + '</div>'
      + jaLine + '</div>';
  }).join('');
}

function pick(ds) {
  sel = sel === ds ? null : ds;
  renderCal();
  renderEvents();
  document.querySelector('.ev-section').scrollIntoView({behavior:'smooth'});
}

document.getElementById('prev').onclick = () => {
  cm--; if (cm<0){cm=11;cy--;} sel=null; renderCal(); renderEvents();
};
document.getElementById('next').onclick = () => {
  cm++; if (cm>11){cm=0;cy++;} sel=null; renderCal(); renderEvents();
};

// Init: jump to first month with events
(function(){
  const now = new Date();
  cy = now.getFullYear(); cm = now.getMonth();
  const prefix = cy + '-' + String(cm+1).padStart(2,'0');
  if (!EVENTS.some(e => e.date_start && e.date_start.startsWith(prefix)) && EVENTS.length) {
    const d = new Date(EVENTS[0].date_start + 'T00:00:00');
    cy = d.getFullYear(); cm = d.getMonth();
  }
  renderCal(); renderEvents();
})();
</script>
</body>
</html>"""


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
    for e in events:
        if e["source"] == "okinawastory" and not e["name_zh"]:
            e["name_zh"] = cache.get(e["url"], "") or translate_ja_zh(e["name"])


# ── 網頁生成 ──────────────────────────────────────────────────────────

def generate_html(events, updated_str):
    events_json = json.dumps(events, ensure_ascii=False)
    html = HTML_TEMPLATE
    html = html.replace("<<<EVENTS_JSON>>>", events_json)
    html = html.replace("<<<UPDATED>>>", updated_str)
    html = html.replace("<<<TOTAL>>>", str(len(events)))
    return html


# ── Telegram ──────────────────────────────────────────────────────────

def fmt_tg(e):
    dt = datetime.strptime(e["date_start"], "%Y-%m-%d")
    end = datetime.strptime(e["date_end"], "%Y-%m-%d")
    wd = WEEKDAYS[dt.weekday()]
    date_str = f"{dt.month}/{dt.day}({wd})"
    if e["date_start"] != e["date_end"]:
        date_str += f"～{end.month}/{end.day}"
    zh = e.get("name_zh") or e["name"]
    flag = "🇯🇵" if e["source"] == "okinawastory" else "🌏"
    return f"📅 {date_str} {flag} [{zh}]({e['url']})\n"


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
                   "updated": datetime.now().isoformat()},
                  f, ensure_ascii=False, indent=2)


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

    os.makedirs("docs", exist_ok=True)
    with open(EVENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_events, f, ensure_ascii=False, indent=2)
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(generate_html(all_events, now.strftime("%Y-%m-%d %H:%M")))
    print(f"📄 網頁已更新：{len(all_events)} 個活動")

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
