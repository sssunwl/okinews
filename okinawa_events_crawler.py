import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
import json
import re
import time
from pathlib import Path

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SEEN_FILE = "seen_events.json"
EVENTS_FILE = "docs/events.json"
HTML_FILE = "docs/index.html"
TEMPLATE_FILE = Path(__file__).with_name("site_template.html")
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
WEEKDAYS = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]

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

# ── HTML 模板 ─────────────────────────────────────────────────────────
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>沖繩年曆 · Okinawa</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🦁</text></svg>">
<style>
:root{
  --bg:#EBF5FA;
  --surface:rgba(255,255,255,0.76);
  --surface-h:rgba(255,255,255,0.96);
  --ocean:#14689A;
  --coral:#E0583A;
  --teal:#1A9E8F;
  --gold:#C8980A;
  --gold-bg:rgba(200,152,10,0.08);
  --gold-border:rgba(200,152,10,0.3);
  --text:#152636;
  --muted:#5C8FA8;
  --border:rgba(20,104,154,0.13);
  --blur:blur(14px);
  --r:12px;
  --hh:56px;
  --sticky-h:96px;
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{
  font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Yu Gothic","Noto Sans TC",sans-serif;
  background:var(--bg);color:var(--text);font-size:14px;line-height:1.6;
  min-height:100vh;overflow-x:hidden;
}
body::before{
  content:'';position:fixed;inset:0;z-index:-2;
  background:
    radial-gradient(ellipse at 8% 15%,rgba(20,104,154,0.11) 0%,transparent 50%),
    radial-gradient(ellipse at 92% 75%,rgba(26,158,143,0.08) 0%,transparent 46%),
    radial-gradient(ellipse at 50% 108%,rgba(245,238,224,0.5) 0%,transparent 45%);
  animation:bgDrift 22s ease-in-out infinite alternate;
}
body::after{
  content:'';position:fixed;inset:0;z-index:-1;pointer-events:none;
  background-image:radial-gradient(circle,rgba(20,104,154,0.04) 1px,transparent 1px);
  background-size:28px 28px;
}
@keyframes bgDrift{0%{opacity:.82}100%{opacity:1;transform:scale(1.018)}}

/* ── Palm decorations ── */
.palm-deco{
  position:fixed;top:50px;pointer-events:none;z-index:85;
  opacity:0.78;filter:drop-shadow(2px 5px 8px rgba(0,50,15,0.2));
}
.palm-l{left:-18px;transform-origin:12% 4%;animation:swayL 5.5s ease-in-out infinite}
.palm-r{right:-18px;transform-origin:88% 4%;animation:swayR 7s ease-in-out infinite;animation-delay:-2.8s}
@keyframes swayL{0%,100%{transform:rotate(-7deg)}50%{transform:rotate(4deg)}}
@keyframes swayR{0%,100%{transform:rotate(6deg)}50%{transform:rotate(-4deg)}}
@media(max-width:1080px){.palm-deco{display:none}}

/* ── Header ── */
header{
  position:fixed;top:0;left:0;right:0;height:var(--hh);z-index:100;
  background:rgba(235,245,250,0.90);
  border-bottom:1px solid rgba(20,104,154,0.15);
  backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur);
  display:flex;align-items:center;justify-content:space-between;padding:0 22px;
}
.logo{display:flex;flex-direction:column;line-height:1.2}
.logo-sub{font-size:9px;color:var(--teal);letter-spacing:.22em;font-weight:600;text-transform:uppercase}
.logo-main{font-size:17px;font-weight:800;color:var(--ocean)}
.header-right{font-size:11px;color:var(--muted)}

/* ── Sticky bar ── */
.sticky-bar{
  position:sticky;top:var(--hh);z-index:90;
  background:rgba(235,245,250,0.90);
  border-bottom:1px solid var(--border);
  backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur);
}
.year-nav{display:flex;align-items:center;gap:5px;padding:8px 16px 4px;overflow-x:auto;scrollbar-width:none}
.year-nav::-webkit-scrollbar{display:none}
.nav-sep{flex:1;min-width:6px}
.month-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:3px;padding:4px 14px 8px}
@media(max-width:480px){.month-grid{grid-template-columns:repeat(4,1fr)}}

.year-btn,.month-btn,.filter-btn{
  flex-shrink:0;background:rgba(255,255,255,0.5);
  border:1px solid var(--border);color:var(--muted);
  cursor:pointer;font-weight:600;transition:all .15s;white-space:nowrap;
}
.year-btn{padding:4px 13px;border-radius:20px;font-size:13px}
.month-btn{padding:5px 4px;border-radius:8px;text-align:center;font-size:12px}
.filter-btn{padding:4px 11px;border-radius:20px;font-size:11.5px;display:flex;align-items:center;gap:3px}
.year-btn.active,.month-btn.active{background:var(--ocean);border-color:var(--ocean);color:#fff}
.filter-btn.f-ti{background:var(--gold);border-color:var(--gold);color:#fff}
.filter-btn.f-ac{background:var(--coral);border-color:var(--coral);color:#fff}
.year-btn:not(.active):hover{background:rgba(20,104,154,0.1);border-color:rgba(20,104,154,0.28);color:var(--ocean);transform:translateY(-1px)}
.month-btn:not(.active):hover{background:rgba(20,104,154,0.1);border-color:rgba(20,104,154,0.28);color:var(--ocean);transform:scale(1.05)}
.filter-btn:not(.f-ti):not(.f-ac):hover{background:rgba(20,104,154,0.1);border-color:rgba(20,104,154,0.28);color:var(--ocean);transform:translateY(-1px)}

/* ── Wave divider ── */
.wave-bar{height:26px;overflow:hidden;pointer-events:none;position:relative}
.wave-bar svg{position:absolute;bottom:0;width:200%;left:0;animation:waveScroll 10s linear infinite}
@keyframes waveScroll{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}

/* ── Content + Two-column layout ── */
.content{max-width:820px;margin:0 auto;padding:16px 16px 100px}

.main-grid{display:flex;flex-direction:column;gap:0}
@media(min-width:660px){
  .main-grid{
    display:grid;
    grid-template-columns:288px 1fr;
    gap:0 20px;
    align-items:start;
  }
  .cal-panel{
    position:sticky;
    top:calc(var(--hh) + var(--sticky-h) + 8px);
  }
}

/* ── Calendar ── */
.cal-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.cal-month-label{font-size:14px;font-weight:700;color:var(--ocean)}
.cal-legend{display:flex;flex-direction:column;gap:3px;font-size:10px;color:var(--muted)}
.cal-legend span{display:flex;align-items:center;gap:3px}
.l-dot{width:6px;height:6px;border-radius:50%;display:inline-block;flex-shrink:0}

.cal-weekdays{display:grid;grid-template-columns:repeat(7,1fr);margin-bottom:3px}
.cal-wd{text-align:center;font-size:10px;font-weight:700;color:var(--muted);padding:3px 0}
.cal-wd:first-child{color:var(--coral)}
.cal-wd:last-child{color:var(--ocean)}

.cal-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:2px;margin-bottom:16px}
.cal-day{
  aspect-ratio:1;display:flex;flex-direction:column;
  align-items:center;justify-content:center;
  border-radius:7px;cursor:pointer;font-size:11.5px;
  transition:all .15s;min-height:28px;position:relative;
}
.cal-day:not(.other-month):hover{
  background:rgba(20,104,154,0.13);
  transform:scale(1.12);
  z-index:2;
  box-shadow:0 2px 8px rgba(20,104,154,0.18);
}
.cal-day.today{background:var(--ocean);color:#fff;font-weight:700;box-shadow:0 0 10px rgba(20,104,154,0.3)}
.cal-day.today:hover{background:var(--ocean);transform:scale(1.1)}
.cal-day.other-month{color:rgba(21,38,54,0.16);cursor:default}
.cal-day.other-month:hover{background:none;transform:none;box-shadow:none}
.cal-day.selected{background:rgba(20,104,154,0.14);border:1.5px solid var(--ocean);color:var(--ocean);font-weight:700}
.cal-day.today.selected{background:var(--ocean);border-color:var(--coral);color:#fff}
.cal-dots{display:flex;gap:1.5px;justify-content:center;flex-wrap:wrap;margin-top:1.5px}
.cal-dot{width:4px;height:4px;border-radius:50%}
.dot-v{background:var(--coral)}
.dot-j{background:var(--teal)}
.dot-t{background:var(--gold)}

/* ── Section label ── */
.sec-label{
  font-size:11px;font-weight:700;color:var(--ocean);letter-spacing:.08em;text-transform:uppercase;
  padding-bottom:7px;border-bottom:1.5px solid rgba(20,104,154,0.18);
  margin-bottom:10px;display:flex;align-items:center;gap:7px;flex-wrap:wrap;
}
.ev-count{background:var(--coral);color:#fff;border-radius:10px;padding:1px 8px;font-size:10px;font-weight:700;letter-spacing:0;text-transform:none}
.filter-hint{font-size:10px;color:var(--muted);font-weight:400;letter-spacing:0;text-transform:none;background:rgba(20,104,154,0.07);border-radius:8px;padding:2px 8px}

/* ── Event items ── */
.ev-item{
  display:flex;align-items:flex-start;gap:10px;
  padding:11px 14px;background:var(--surface);
  border-radius:var(--r);border:1px solid var(--border);
  backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur);
  transition:all .2s;margin-bottom:7px;
  animation:fadeUp .3s ease both;cursor:default;
}
.ev-item.today-is{border-left:3px solid var(--gold);background:rgba(255,252,235,0.80)}
.ev-item.vtype{border-left:3px solid var(--coral)}
.ev-item.jtype{border-left:3px solid var(--teal)}

/* per-type hover */
.ev-item.today-is:hover{
  background:rgba(255,253,240,0.96);transform:translateY(-2px);
  box-shadow:0 6px 24px rgba(200,152,10,0.16),0 0 0 1px rgba(200,152,10,0.18);
}
.ev-item.vtype:hover{
  background:var(--surface-h);transform:translateY(-2px);
  box-shadow:0 6px 24px rgba(224,88,58,0.14),0 0 0 1px rgba(224,88,58,0.14);
}
.ev-item.jtype:hover{
  background:var(--surface-h);transform:translateY(-2px);
  box-shadow:0 6px 24px rgba(26,158,143,0.14),0 0 0 1px rgba(26,158,143,0.12);
}

.ev-date{flex-shrink:0;width:50px;font-size:10.5px;color:var(--ocean);font-weight:700;text-align:center;line-height:1.45;padding-top:2px}
.ev-body{flex:1;min-width:0}
.ev-zh{font-size:13px;font-weight:700;color:var(--text);line-height:1.4;margin-bottom:2px;display:block;text-decoration:none}
a.ev-zh:hover{color:var(--ocean)}
.ev-desc{font-size:11px;color:var(--muted);line-height:1.55;margin:3px 0 5px}
.ev-ja{font-size:11px;color:var(--muted)}
.ev-ja a{color:var(--muted);text-decoration:none}
.ev-ja a:hover{color:var(--teal);text-decoration:underline}
.ev-meta{display:flex;align-items:center;gap:6px;margin-top:4px}
.ev-cat{font-size:10px;background:var(--gold-bg);color:var(--gold);border:1px solid var(--gold-border);border-radius:6px;padding:1px 7px;font-weight:600}
.ev-stars{font-size:10px;color:var(--gold);letter-spacing:.5px}

.empty{text-align:center;padding:44px;color:var(--muted);font-size:13px}

/* ── Footer ── */
footer{text-align:center;padding:22px 16px;font-size:11px;color:var(--muted);border-top:1px solid var(--border)}

@keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
@media(max-width:380px){.logo-main{font-size:15px}}
</style>
</head>
<body>

<header>
  <div class="logo">
    <span class="logo-sub">Okinawa Calendar</span>
    <span class="logo-main">🦁 沖繩年曆</span>
  </div>
  <div class="header-right">更新 <<<UPDATED>>></div>
</header>

<!-- Palm leaf decorations -->
<div class="palm-deco palm-l">
<svg xmlns="http://www.w3.org/2000/svg" width="168" height="330" viewBox="0 0 168 330">
  <path d="M92,330 C90,275 86,210 82,152 C78,106 73,68 67,28" stroke="#7A5118" stroke-width="6" fill="none" stroke-linecap="round"/>
  <circle cx="73" cy="52" r="9" fill="#B8820A" opacity="0.72"/><circle cx="85" cy="42" r="7" fill="#C89010" opacity="0.65"/>
  <path d="M70,68 C44,50 8,50 -16,64 C10,46 46,46 70,62Z" fill="#2A7832" opacity="0.92"/>
  <path d="M76,57 C102,36 136,33 160,48 C133,31 99,33 76,52Z" fill="#338C3C" opacity="0.88"/>
  <path d="M64,90 C34,100 -4,122 -25,153 C-2,118 35,96 64,85Z" fill="#2A7832" opacity="0.84"/>
  <path d="M78,87 C110,92 146,113 166,142 C143,110 108,90 78,82Z" fill="#338C3C" opacity="0.80"/>
  <path d="M58,118 C26,136 -10,173 -28,215 C-7,168 28,133 58,112Z" fill="#246B2C" opacity="0.76"/>
  <path d="M73,114 C102,128 138,163 154,204 C135,160 102,126 73,109Z" fill="#2A7832" opacity="0.70"/>
  <path d="M50,152 C20,178 -6,220 -16,262 C-3,217 23,174 50,146Z" fill="#1E5C24" opacity="0.62"/>
</svg>
</div>
<div class="palm-deco palm-r">
<svg xmlns="http://www.w3.org/2000/svg" width="168" height="330" viewBox="0 0 168 330">
  <path d="M76,330 C78,275 82,210 86,152 C90,106 95,68 101,28" stroke="#7A5118" stroke-width="6" fill="none" stroke-linecap="round"/>
  <circle cx="95" cy="52" r="9" fill="#B8820A" opacity="0.72"/><circle cx="83" cy="42" r="7" fill="#C89010" opacity="0.65"/>
  <path d="M98,68 C124,50 160,50 184,64 C158,46 122,46 98,62Z" fill="#2A7832" opacity="0.92"/>
  <path d="M92,57 C66,36 32,33 8,48 C35,31 69,33 92,52Z" fill="#338C3C" opacity="0.88"/>
  <path d="M104,90 C134,100 172,122 193,153 C170,118 133,96 104,85Z" fill="#2A7832" opacity="0.84"/>
  <path d="M90,87 C58,92 22,113 2,142 C25,110 60,90 90,82Z" fill="#338C3C" opacity="0.80"/>
  <path d="M110,118 C142,136 178,173 196,215 C175,168 140,133 110,112Z" fill="#246B2C" opacity="0.76"/>
  <path d="M95,114 C66,128 30,163 14,204 C33,160 66,126 95,109Z" fill="#2A7832" opacity="0.70"/>
  <path d="M118,152 C148,178 174,220 184,262 C171,217 145,174 118,146Z" fill="#1E5C24" opacity="0.62"/>
</svg>
</div>

<!-- Year + Month selector -->
<div class="sticky-bar" id="sticky-bar">
  <div class="year-nav" id="year-nav"></div>
  <div class="month-grid" id="month-grid"></div>
</div>

<!-- Wave divider -->
<div class="wave-bar">
<svg height="26" viewBox="0 0 2880 26" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M0,13 C240,24 480,2 720,13 C960,24 1200,2 1440,13 C1680,24 1920,2 2160,13 C2400,24 2640,2 2880,13 V26 H0Z" fill="rgba(20,104,154,0.06)"/>
  <path d="M0,18 C360,8 720,24 1080,18 C1440,12 1800,24 2160,18 C2520,12 2880,22 2880,18 V26 H0Z" fill="rgba(26,158,143,0.04)"/>
</svg>
</div>

<div class="content">
  <div class="main-grid">
    <!-- 左欄：月曆 -->
    <div class="cal-panel" id="cal-panel">
      <div class="cal-header">
        <span class="cal-month-label" id="cal-label"></span>
        <div class="cal-legend">
          <span><span class="l-dot" style="background:var(--gold)"></span>今天是…</span>
          <span><span class="l-dot" style="background:var(--coral)"></span>Visit Okinawa</span>
          <span><span class="l-dot" style="background:var(--teal)"></span>おきなわ物語</span>
        </div>
      </div>
      <div class="cal-weekdays">
        <div class="cal-wd">日</div><div class="cal-wd">一</div><div class="cal-wd">二</div>
        <div class="cal-wd">三</div><div class="cal-wd">四</div><div class="cal-wd">五</div><div class="cal-wd">六</div>
      </div>
      <div class="cal-grid" id="cal-grid"></div>
    </div>
    <!-- 右欄：活動列表 -->
    <div class="ev-panel">
      <div class="sec-label" id="ev-label">
        本月活動<span class="ev-count" id="ev-count">0</span>
        <span class="filter-hint" id="filter-hint" style="display:none"></span>
      </div>
      <div id="ev-list"></div>
    </div>
  </div>
</div>

<footer>共 <<<TOTAL>>> 筆資料 &nbsp;·&nbsp; 每日 08:00 JST 自動更新 &nbsp;·&nbsp; 🦁 Suniverse</footer>

<script type="application/json" id="ev-data"><<<EVENTS_JSON>>></script>
<script>
const EVENTS = JSON.parse(document.getElementById('ev-data').textContent);
const byDate = {};
EVENTS.forEach(e => {
  if(!byDate[e.date_start]) byDate[e.date_start] = [];
  byDate[e.date_start].push(e);
});

const WD = ['日','一','二','三','四','五','六'];
const MN = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];

const actMonths = [...new Set(
  EVENTS.filter(e => e.source !== 'today_is').map(e => e.date_start.slice(0,7))
)].sort();
const allMonths = [...new Set(EVENTS.map(e => e.date_start.slice(0,7)))].sort();
const years     = [...new Set(allMonths.map(m => m.slice(0,4)))];

let cy, cm, selDate = null, viewMode = null;

function pad(n){ return String(n).padStart(2,'0'); }

// measure sticky bar height and update CSS var so cal-panel sticks correctly
function updateStickyOffset(){
  const bar = document.getElementById('sticky-bar');
  if(!bar) return;
  const h = bar.getBoundingClientRect().height;
  document.documentElement.style.setProperty('--sticky-h', h + 'px');
}

// ── Nav ──────────────────────────────────────────────────────────────
function buildNav(){
  const yn = document.getElementById('year-nav');
  const mg = document.getElementById('month-grid');

  yn.innerHTML =
    years.map(y =>
      `<button class="year-btn${parseInt(y)===cy&&!viewMode?' active':''}"
         onclick="setYear('${y}')">${y}</button>`
    ).join('') +
    `<div class="nav-sep"></div>
     <button class="filter-btn${viewMode==='today_is'?' f-ti':''}"
       onclick="toggleFilter('today_is')">🌟 今天是…</button>
     <button class="filter-btn${viewMode==='activity'?' f-ac':''}"
       onclick="toggleFilter('activity')">🌺 沖繩活動</button>`;

  const myActMonths = actMonths.filter(m => m.startsWith(cy));
  mg.innerHTML = Array.from({length:12}, (_,i) => {
    const m   = i + 1;
    const key = cy + '-' + pad(m);
    const has = myActMonths.includes(key);
    const act = !viewMode && m-1 === cm;
    return `<button class="month-btn${act?' active':''}"
      onclick="${has ? `setMonth(${i})` : 'void(0)'}"
      style="${has ? '' : 'opacity:.28;cursor:default'}">${m}月</button>`;
  }).join('');

  // re-measure after DOM updates
  requestAnimationFrame(updateStickyOffset);
}

function setYear(y){
  cy = parseInt(y); viewMode = null;
  const first = actMonths.find(m => m.startsWith(cy));
  cm = first ? parseInt(first.slice(5,7)) - 1 : 0;
  selDate = null; buildNav(); renderCal(); renderEvents();
}
function setMonth(m){
  cm = m; selDate = null; viewMode = null;
  buildNav(); renderCal(); renderEvents();
}
function toggleFilter(type){
  viewMode = viewMode === type ? null : type;
  selDate = null; buildNav(); renderCal(); renderEvents();
}

// ── Calendar ─────────────────────────────────────────────────────────
function renderCal(){
  document.getElementById('cal-label').textContent = cy + '年' + MN[cm];
  const first = new Date(cy, cm, 1);
  const last  = new Date(cy, cm+1, 0);
  const now   = new Date();
  const dow   = first.getDay();
  let html = '';

  const prevLast = new Date(cy, cm, 0).getDate();
  for(let i = dow-1; i >= 0; i--)
    html += `<div class="cal-day other-month"><span>${prevLast-i}</span></div>`;

  for(let d = 1; d <= last.getDate(); d++){
    const ds      = cy + '-' + pad(cm+1) + '-' + pad(d);
    const isToday = d===now.getDate() && cm===now.getMonth() && cy===now.getFullYear();
    const isSel   = ds === selDate;
    const evs     = byDate[ds] || [];
    const dots    = evs.slice(0,5).map(e => {
      const c = e.source==='today_is' ? 'dot-t' : e.source==='okinawastory' ? 'dot-j' : 'dot-v';
      return `<div class="cal-dot ${c}"></div>`;
    }).join('');
    html += `<div class="cal-day${isToday?' today':''}${isSel?' selected':''}" onclick="pickDay('${ds}')">
      <span>${d}</span><div class="cal-dots">${dots}</div></div>`;
  }

  const fill = 42 - dow - last.getDate();
  for(let d = 1; d <= fill; d++)
    html += `<div class="cal-day other-month"><span>${d}</span></div>`;

  document.getElementById('cal-grid').innerHTML = html;
}

function pickDay(ds){
  selDate = selDate === ds ? null : ds;
  viewMode = null; buildNav(); renderCal(); renderEvents();
  // scroll to events panel
  document.getElementById('ev-label').scrollIntoView({behavior:'smooth', block:'start'});
}

// ── Events ────────────────────────────────────────────────────────────
function fmtDate(s){
  if(!s) return '';
  const d = new Date(s + 'T00:00:00');
  return (d.getMonth()+1) + '/' + d.getDate() + '(' + WD[d.getDay()] + ')';
}

function renderEvents(){
  const list  = document.getElementById('ev-list');
  const hint  = document.getElementById('filter-hint');
  let evs, labelText, hintText = '';

  if(viewMode === 'today_is'){
    evs = EVENTS.filter(e => e.source==='today_is')
                .sort((a,b) => a.date_start.localeCompare(b.date_start));
    labelText = '🌟 今天是… 全系列';
    hintText  = '顯示全年度';
  } else if(viewMode === 'activity'){
    evs = EVENTS.filter(e => e.source!=='today_is')
                .sort((a,b) => a.date_start.localeCompare(b.date_start));
    labelText = '🌺 沖繩活動 全覽';
    hintText  = '顯示全時段';
  } else if(selDate){
    const all = byDate[selDate] || [];
    evs = [
      ...all.filter(e => e.source==='today_is'),
      ...all.filter(e => e.source!=='today_is'),
    ];
    labelText = fmtDate(selDate);
  } else {
    const prefix = cy + '-' + pad(cm+1);
    const all = EVENTS.filter(e => e.date_start && e.date_start.startsWith(prefix));
    evs = [
      ...all.filter(e => e.source==='today_is').sort((a,b)=>a.date_start.localeCompare(b.date_start)),
      ...all.filter(e => e.source!=='today_is').sort((a,b)=>a.date_start.localeCompare(b.date_start)),
    ];
    labelText = cy + '年' + MN[cm] + '活動';
  }

  const lbl = document.getElementById('ev-label');
  lbl.childNodes[0].textContent = labelText;
  document.getElementById('ev-count').textContent = evs.length;
  hint.textContent  = hintText;
  hint.style.display = hintText ? 'inline-block' : 'none';

  if(!evs.length){
    list.innerHTML = '<div class="empty">🌊 這裡還沒有資料</div>';
    return;
  }

  list.innerHTML = evs.map((e, i) => {
    if(e.source === 'today_is'){
      const filled = e.stars || 0;
      const stars  = '★'.repeat(filled) + '☆'.repeat(5-filled);
      const desc   = e.description ? `<div class="ev-desc">${e.description}</div>` : '';
      return `<div class="ev-item today-is" style="animation-delay:${i*0.028}s">
        <div class="ev-date">${fmtDate(e.date_start)}</div>
        <div class="ev-body">
          <span class="ev-zh">${e.name_zh||e.name}</span>
          ${desc}
          <div class="ev-meta">
            <span class="ev-cat">${e.category||''}</span>
            <span class="ev-stars">${stars}</span>
          </div>
        </div>
      </div>`;
    }
    const isJ  = e.source==='okinawastory';
    const zh   = e.name_zh||e.name;
    const end  = (e.date_end && e.date_end!==e.date_start)
      ? '～'+(()=>{const d=new Date(e.date_end+'T00:00:00');return(d.getMonth()+1)+'/'+d.getDate()})()
      : '';
    const dtag = fmtDate(e.date_start)+end;
    const zhEl = e.url
      ? `<a class="ev-zh" href="${e.url}" target="_blank" rel="noopener">${zh}</a>`
      : `<span class="ev-zh">${zh}</span>`;
    const jaEl = (isJ && e.name!==zh)
      ? `<div class="ev-ja"><a href="${e.url}" target="_blank" rel="noopener">${e.name}</a></div>` : '';
    return `<div class="ev-item ${isJ?'jtype':'vtype'}" style="animation-delay:${i*0.028}s">
      <div class="ev-date">${dtag}</div>
      <div class="ev-body">${zhEl}${jaEl}</div>
    </div>`;
  }).join('');
}

// ── Init ──────────────────────────────────────────────────────────────
(function(){
  const now = new Date();
  cy = now.getFullYear(); cm = now.getMonth();
  const prefix = cy + '-' + pad(cm+1);
  if(!EVENTS.some(e => e.source!=='today_is' && e.date_start && e.date_start.startsWith(prefix))
     && actMonths.length){
    cy = parseInt(actMonths[0].slice(0,4));
    cm = parseInt(actMonths[0].slice(5,7)) - 1;
  }
  buildNav(); renderCal(); renderEvents();
  window.addEventListener('resize', updateStickyOffset);
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
            return {e["url"]: e.get("name_zh", "") for e in json.load(f) if e.get("url")}
    return {}


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

ENRICH_FIELDS = ("image", "location", "price", "description")


def enrich_visitokinawa(url):
    """從 visitokinawajapan.com 活動詳情頁擷取地點、費用、圖片與介紹。"""
    out = {"image": "", "location": "", "price": "", "description": ""}
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

    return out


def enrich_okinawastory(url):
    """從 okinawastory.jp 活動詳情頁擷取地點、費用、圖片與介紹（日文轉繁中）。"""
    out = {"image": "", "location": "", "price": "", "description": ""}
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
            facility[label.get_text(strip=True)] = pre.get_text(" ", strip=True)

    venue = facility.get("開催場所", "")
    address = facility.get("住所", "")
    area = facility.get("エリア", "")
    out["location"] = " ・ ".join(p for p in (venue or area, address) if p)
    price_ja = facility.get("料金", "")
    out["price"] = "免費" if price_ja in ("無料", "無料。") else price_ja

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
    return not existing_event.get("image") and not existing_event.get("location")


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
            "description": "", "image": "", "location": "", "price": "",
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
                "description": "", "image": "", "location": "", "price": "",
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

def generate_html(events, updated_str):
    events_json = json.dumps(events, ensure_ascii=False)
    events_json = events_json.replace("</script>", "<\\/script>")
    html = TEMPLATE_FILE.read_text(encoding="utf-8")
    html = html.replace("<<<EVENTS_JSON>>>", events_json)
    html = html.replace("<<<UPDATED>>>", updated_str)
    html = html.replace("<<<TOTAL>>>", str(len(events)))
    return html


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
        with open(EVENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(events, f, ensure_ascii=False, indent=2)
        with open(HTML_FILE, "w", encoding="utf-8") as f:
            f.write(generate_html(events, now.strftime("%Y-%m-%d %H:%M")))
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

    os.makedirs("docs", exist_ok=True)
    with open(EVENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_events, f, ensure_ascii=False, indent=2)
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(generate_html(all_events, now.strftime("%Y-%m-%d %H:%M")))
    print("📄 網頁更新完成")

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
