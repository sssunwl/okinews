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

# ── 今天是… 固定年曆資料 ────────────────────────────────────────────
# (月, 日, 中文名, emoji, 分類, 推薦星數)
TODAY_IS_DATA = [
    (5, 18, "國際博物館日",    "🎨", "文化", 3),
    (5, 20, "森林日",          "🌳", "自然", 4),
    (5, 21, "小滿",            "🌾", "節氣", 5),
    (5, 22, "國際生物多樣性日","🪸", "海洋", 5),
    (5, 25, "主婦休息日",      "☕", "生活", 2),
    (5, 26, "風呂日",          "♨️", "文化", 2),
    (5, 29, "幸福日",          "😊", "生活", 3),
    (5, 30, "零垃圾日",        "♻️", "永續", 5),
    (6,  1, "泡盛之日",        "🍶", "沖繩", 5),
    (6,  4, "蟲牙預防日",      "🦷", "文化", 2),
    (6,  8, "世界海洋日",      "🌊", "海洋", 5),
    (6, 11, "國際玩樂日",      "🎮", "生活", 2),
    (6, 15, "沖繩戰跡紀念",    "🕊️", "歷史", 4),
    (6, 21, "夏至",            "☀️", "節氣", 5),
    (6, 23, "慰靈之日",        "🕊️", "沖繩", 5),
    (6, 26, "露天風呂日",      "♨️", "文化", 2),
    (6, 30, "夏越之祓",        "⛩️", "傳統", 5),
    (7,  1, "海開季",          "🏖️", "夏日", 5),
    (7,  7, "七夕",            "🎋", "傳統", 5),
    (7, 10, "納豆日",          "🫘", "文化", 2),
    (7, 15, "海之日",          "🌊", "傳統", 5),
    (7, 20, "漢堡日",          "🍔", "文化", 3),
    (7, 22, "大暑",            "☀️", "節氣", 4),
    (7, 25, "刨冰日",          "🍧", "夏日", 5),
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
  --gold-border:rgba(200,152,10,0.32);
  --text:#152636;
  --muted:#5C8FA8;
  --border:rgba(20,104,154,0.13);
  --blur:blur(14px);
  --r:12px;
  --hh:56px;
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{
  font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Yu Gothic","Noto Sans TC",sans-serif;
  background:var(--bg);color:var(--text);font-size:14px;line-height:1.6;
  min-height:100vh;overflow-x:hidden;
}

/* ── Background ── */
body::before{
  content:'';position:fixed;inset:0;z-index:-2;
  background:
    radial-gradient(ellipse at 8% 15%,rgba(20,104,154,0.11) 0%,transparent 50%),
    radial-gradient(ellipse at 92% 75%,rgba(26,158,143,0.08) 0%,transparent 46%),
    radial-gradient(ellipse at 50% 108%,rgba(245,238,224,0.55) 0%,transparent 45%);
  animation:bgDrift 22s ease-in-out infinite alternate;
}
/* dot-grid texture for depth */
body::after{
  content:'';position:fixed;inset:0;z-index:-1;pointer-events:none;
  background-image:
    radial-gradient(circle,rgba(20,104,154,0.045) 1px,transparent 1px);
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
/* only show palms when there's enough margin space */
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
.logo-main{font-size:17px;font-weight:800;color:var(--ocean);letter-spacing:.03em}
.header-right{font-size:11px;color:var(--muted)}

/* ── Sticky bar ── */
.sticky-bar{
  position:sticky;top:var(--hh);z-index:90;
  background:rgba(235,245,250,0.90);
  border-bottom:1px solid var(--border);
  backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur);
}
.year-nav{
  display:flex;align-items:center;gap:5px;
  padding:8px 16px 4px;overflow-x:auto;scrollbar-width:none;
}
.year-nav::-webkit-scrollbar{display:none}
.nav-sep{flex:1;min-width:6px}
.month-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:3px;padding:4px 14px 8px}
@media(max-width:480px){.month-grid{grid-template-columns:repeat(4,1fr)}}

.year-btn,.month-btn,.filter-btn{
  flex-shrink:0;background:rgba(255,255,255,0.5);
  border:1px solid var(--border);color:var(--muted);
  cursor:pointer;font-weight:600;transition:all .17s;white-space:nowrap;
}
.year-btn{padding:4px 13px;border-radius:20px;font-size:13px}
.month-btn{padding:5px 4px;border-radius:8px;text-align:center;font-size:12px}
.filter-btn{padding:4px 11px;border-radius:20px;font-size:11.5px;display:flex;align-items:center;gap:3px}
.year-btn.active,.month-btn.active{background:var(--ocean);border-color:var(--ocean);color:#fff}
.filter-btn.f-ti{background:var(--gold);border-color:var(--gold);color:#fff}
.filter-btn.f-ac{background:var(--coral);border-color:var(--coral);color:#fff}
.year-btn:not(.active):hover,.month-btn:not(.active):hover,
.filter-btn:not(.f-ti):not(.f-ac):hover{
  background:rgba(20,104,154,0.1);border-color:rgba(20,104,154,0.28);color:var(--ocean);
}

/* ── Wave divider ── */
.wave-bar{
  height:26px;overflow:hidden;pointer-events:none;position:relative;
  background:transparent;
}
.wave-bar svg{position:absolute;bottom:0;width:200%;left:0;animation:waveScroll 10s linear infinite}
@keyframes waveScroll{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}

/* ── Content ── */
.content{max-width:780px;margin:0 auto;padding:16px 16px 100px}

/* ── Calendar ── */
.cal-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.cal-month-label{font-size:15px;font-weight:700;color:var(--ocean)}
.cal-legend{display:flex;gap:9px;font-size:10px;color:var(--muted);align-items:center;flex-wrap:wrap}
.cal-legend span{display:flex;align-items:center;gap:3px}
.l-dot{width:6px;height:6px;border-radius:50%;display:inline-block;flex-shrink:0}

.cal-weekdays{display:grid;grid-template-columns:repeat(7,1fr);margin-bottom:3px}
.cal-wd{text-align:center;font-size:10px;font-weight:700;color:var(--muted);padding:4px 0}
.cal-wd:first-child{color:var(--coral)}
.cal-wd:last-child{color:var(--ocean)}

.cal-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:2px;margin-bottom:20px}
.cal-day{
  aspect-ratio:1;display:flex;flex-direction:column;
  align-items:center;justify-content:center;
  border-radius:8px;cursor:pointer;font-size:12px;
  transition:background .14s;min-height:32px;
}
.cal-day:hover{background:rgba(20,104,154,0.09)}
.cal-day.today{background:var(--ocean);color:#fff;font-weight:700;box-shadow:0 0 10px rgba(20,104,154,0.28)}
.cal-day.other-month{color:rgba(21,38,54,0.18);cursor:default}
.cal-day.other-month:hover{background:none}
.cal-day.selected{background:rgba(20,104,154,0.13);border:1.5px solid var(--ocean);color:var(--ocean);font-weight:700}
.cal-day.today.selected{background:var(--ocean);border-color:var(--coral);color:#fff}
.cal-dots{display:flex;gap:2px;justify-content:center;flex-wrap:wrap;margin-top:2px}
.cal-dot{width:5px;height:5px;border-radius:50%}
.dot-v{background:var(--coral)}
.dot-j{background:var(--teal)}
.dot-t{background:var(--gold)}

/* ── Section label ── */
.sec-label{
  font-size:11px;font-weight:700;color:var(--ocean);letter-spacing:.1em;text-transform:uppercase;
  padding-bottom:7px;border-bottom:1.5px solid rgba(20,104,154,0.18);
  margin-bottom:10px;display:flex;align-items:center;gap:7px;flex-wrap:wrap;
}
.ev-count{
  background:var(--coral);color:#fff;border-radius:10px;
  padding:1px 8px;font-size:10px;font-weight:700;letter-spacing:0;text-transform:none;
}
.filter-hint{
  font-size:10px;color:var(--muted);font-weight:400;letter-spacing:0;text-transform:none;
  background:rgba(20,104,154,0.07);border-radius:8px;padding:2px 8px;
}

/* ── Event items ── */
.ev-item{
  display:flex;align-items:flex-start;gap:10px;
  padding:11px 14px;background:var(--surface);
  border-radius:var(--r);border:1px solid var(--border);
  backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur);
  transition:all .2s;margin-bottom:7px;animation:fadeUp .3s ease both;
}
.ev-item:hover{
  background:var(--surface-h);
  box-shadow:0 4px 20px rgba(20,104,154,0.10),0 1px 4px rgba(0,0,0,0.05);
  transform:translateY(-1px);
}
.ev-item.today-is{border-left:3px solid var(--gold);background:rgba(255,252,235,0.80)}
.ev-item.today-is:hover{box-shadow:0 4px 16px rgba(200,152,10,0.12)}
.ev-item.vtype{border-left:3px solid var(--coral)}
.ev-item.jtype{border-left:3px solid var(--teal)}

.ev-date{flex-shrink:0;width:54px;font-size:11px;color:var(--ocean);font-weight:700;text-align:center;line-height:1.45;padding-top:1px}
.ev-body{flex:1;min-width:0}
.ev-zh{font-size:13.5px;font-weight:700;color:var(--text);line-height:1.4;margin-bottom:3px;display:block;text-decoration:none}
a.ev-zh:hover{color:var(--ocean)}
.ev-ja{font-size:11px;color:var(--muted);margin-top:1px}
.ev-ja a{color:var(--muted);text-decoration:none}
.ev-ja a:hover{color:var(--teal);text-decoration:underline}
.ev-meta{display:flex;align-items:center;gap:6px;margin-top:5px}
.ev-cat{font-size:10px;background:var(--gold-bg);color:var(--gold);border:1px solid var(--gold-border);border-radius:6px;padding:1px 7px;font-weight:600}
.ev-stars{font-size:10px;color:var(--gold);letter-spacing:.5px}

.empty{text-align:center;padding:44px;color:var(--muted);font-size:13px}

/* ── Footer ── */
footer{
  text-align:center;padding:22px 16px;font-size:11px;color:var(--muted);
  border-top:1px solid var(--border);
}

@keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
@media(max-width:380px){.cal-day{min-height:26px;font-size:10px}.logo-main{font-size:15px}}
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

<!-- Palm leaf decorations (foreground, swaying) -->
<div class="palm-deco palm-l">
<svg xmlns="http://www.w3.org/2000/svg" width="168" height="330" viewBox="0 0 168 330">
  <path d="M92,330 C90,275 86,210 82,152 C78,106 73,68 67,28"
    stroke="#7A5118" stroke-width="6" fill="none" stroke-linecap="round"/>
  <circle cx="73" cy="52" r="9" fill="#B8820A" opacity="0.72"/>
  <circle cx="85" cy="42" r="7" fill="#C89010" opacity="0.65"/>
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
  <path d="M76,330 C78,275 82,210 86,152 C90,106 95,68 101,28"
    stroke="#7A5118" stroke-width="6" fill="none" stroke-linecap="round"/>
  <circle cx="95" cy="52" r="9" fill="#B8820A" opacity="0.72"/>
  <circle cx="83" cy="42" r="7" fill="#C89010" opacity="0.65"/>
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
<div class="sticky-bar">
  <div class="year-nav" id="year-nav"></div>
  <div class="month-grid" id="month-grid"></div>
</div>

<!-- Wave divider -->
<div class="wave-bar">
<svg height="26" viewBox="0 0 2880 26" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M0,13 C240,24 480,2 720,13 C960,24 1200,2 1440,13 C1680,24 1920,2 2160,13 C2400,24 2640,2 2880,13 V26 H0Z"
    fill="rgba(20,104,154,0.06)"/>
  <path d="M0,18 C360,8 720,24 1080,18 C1440,12 1800,24 2160,18 C2520,12 2880,22 2880,18 V26 H0Z"
    fill="rgba(26,158,143,0.04)"/>
</svg>
</div>

<div class="content">
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

  <div class="sec-label" id="ev-label">
    本月活動<span class="ev-count" id="ev-count">0</span>
    <span class="filter-hint" id="filter-hint" style="display:none"></span>
  </div>
  <div id="ev-list"></div>
</div>

<footer>共 <<<TOTAL>>> 筆資料 &nbsp;·&nbsp; 每日 08:00 JST 自動更新 &nbsp;·&nbsp; 🦁 Suniverse</footer>

<script type="application/json" id="ev-data"><<<EVENTS_JSON>>></script>
<script>
const EVENTS = JSON.parse(document.getElementById('ev-data').textContent);
const byDate = {};
EVENTS.forEach(e => {
  if (!byDate[e.date_start]) byDate[e.date_start] = [];
  byDate[e.date_start].push(e);
});

const WD  = ['日','一','二','三','四','五','六'];
const MN  = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];

// months that have real (non-today_is) events
const actMonths = [...new Set(
  EVENTS.filter(e => e.source !== 'today_is').map(e => e.date_start.slice(0,7))
)].sort();
const allMonths = [...new Set(EVENTS.map(e => e.date_start.slice(0,7)))].sort();
const years     = [...new Set(allMonths.map(m => m.slice(0,4)))];

let cy, cm, selDate = null, viewMode = null; // null | 'today_is' | 'activity'

function pad(n){ return String(n).padStart(2,'0'); }

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
  mg.innerHTML = Array.from({length:12}, (_, i) => {
    const m = i + 1;
    const key = cy + '-' + pad(m);
    const has = myActMonths.includes(key);
    const act = !viewMode && m-1 === cm;
    return `<button class="month-btn${act?' active':''}"
      onclick="${has ? `setMonth(${i})` : 'void(0)'}"
      style="${has ? '' : 'opacity:.28;cursor:default'}">${m}月</button>`;
  }).join('');
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
    html += `<div class="cal-day other-month"><span>${prevLast - i}</span></div>`;

  for(let d = 1; d <= last.getDate(); d++){
    const ds = cy + '-' + pad(cm+1) + '-' + pad(d);
    const isToday = d === now.getDate() && cm === now.getMonth() && cy === now.getFullYear();
    const isSel   = ds === selDate;
    const evs     = byDate[ds] || [];
    const dots    = evs.slice(0,5).map(e => {
      const c = e.source === 'today_is' ? 'dot-t'
              : e.source === 'okinawastory' ? 'dot-j' : 'dot-v';
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
    evs = EVENTS.filter(e => e.source === 'today_is')
                .sort((a,b) => a.date_start.localeCompare(b.date_start));
    labelText = '🌟 今天是… 全系列';
    hintText  = '顯示全年度';
  } else if(viewMode === 'activity'){
    evs = EVENTS.filter(e => e.source !== 'today_is')
                .sort((a,b) => a.date_start.localeCompare(b.date_start));
    labelText = '🌺 沖繩活動 全覽';
    hintText  = '顯示全時段';
  } else if(selDate){
    const all = byDate[selDate] || [];
    evs = [
      ...all.filter(e => e.source === 'today_is'),
      ...all.filter(e => e.source !== 'today_is'),
    ];
    labelText = fmtDate(selDate);
  } else {
    const prefix = cy + '-' + pad(cm+1);
    const all = EVENTS.filter(e => e.date_start && e.date_start.startsWith(prefix));
    evs = [
      ...all.filter(e => e.source === 'today_is').sort((a,b) => a.date_start.localeCompare(b.date_start)),
      ...all.filter(e => e.source !== 'today_is').sort((a,b) => a.date_start.localeCompare(b.date_start)),
    ];
    labelText = cy + '年' + MN[cm] + '活動';
  }

  const lbl = document.getElementById('ev-label');
  lbl.childNodes[0].textContent = labelText;
  document.getElementById('ev-count').textContent = evs.length;
  hint.textContent = hintText;
  hint.style.display = hintText ? 'inline-block' : 'none';

  if(!evs.length){
    list.innerHTML = '<div class="empty">🌊 這裡還沒有資料</div>';
    return;
  }

  list.innerHTML = evs.map((e, i) => {
    if(e.source === 'today_is'){
      const filled = e.stars || 0;
      const stars  = '★'.repeat(filled) + '☆'.repeat(5 - filled);
      return `<div class="ev-item today-is" style="animation-delay:${i*0.03}s">
        <div class="ev-date">${fmtDate(e.date_start)}</div>
        <div class="ev-body">
          <span class="ev-zh">${e.name_zh || e.name}</span>
          <div class="ev-meta">
            <span class="ev-cat">${e.category || ''}</span>
            <span class="ev-stars">${stars}</span>
          </div>
        </div>
      </div>`;
    }
    const isJ  = e.source === 'okinawastory';
    const zh   = e.name_zh || e.name;
    const end  = (e.date_end && e.date_end !== e.date_start)
      ? '～' + (()=>{ const d=new Date(e.date_end+'T00:00:00'); return (d.getMonth()+1)+'/'+d.getDate(); })()
      : '';
    const dtag = fmtDate(e.date_start) + end;
    const zhEl = e.url
      ? `<a class="ev-zh" href="${e.url}" target="_blank" rel="noopener">${zh}</a>`
      : `<span class="ev-zh">${zh}</span>`;
    const jaEl = (isJ && e.name !== zh)
      ? `<div class="ev-ja"><a href="${e.url}" target="_blank" rel="noopener">${e.name}</a></div>` : '';
    return `<div class="ev-item ${isJ?'jtype':'vtype'}" style="animation-delay:${i*0.03}s">
      <div class="ev-date">${dtag}</div>
      <div class="ev-body">${zhEl}${jaEl}</div>
    </div>`;
  }).join('');
}

// ── Init ──────────────────────────────────────────────────────────────
(function(){
  const now = new Date();
  cy = now.getFullYear();
  cm = now.getMonth();
  // if current month has no activity events, jump to first available month
  const prefix = cy + '-' + pad(cm+1);
  if(!EVENTS.some(e => e.source !== 'today_is' && e.date_start && e.date_start.startsWith(prefix))
     && actMonths.length){
    cy = parseInt(actMonths[0].slice(0,4));
    cm = parseInt(actMonths[0].slice(5,7)) - 1;
  }
  buildNav(); renderCal(); renderEvents();
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


# ── 今天是… 生成（年份：前1年～後2年，確保年曆覆蓋足夠範圍） ────────

def get_today_is_events():
    events = []
    now = datetime.now()
    for year in range(now.year - 1, now.year + 2):
        for (month, day, zh_name, emoji, cat, stars) in TODAY_IS_DATA:
            try:
                dt = datetime(year, month, day)
            except ValueError:
                continue
            events.append({
                "name":       f"今天是 {emoji} {zh_name}",
                "name_zh":    f"{emoji} {zh_name}",
                "date_start": to_iso(dt),
                "date_end":   to_iso(dt),
                "url":        "",
                "source":     "today_is",
                "category":   cat,
                "stars":      stars,
            })
    return events


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
        end_dt   = parse_iso(parts[-1])
        if not start_dt or not end_dt:
            continue
        if end_dt < now or start_dt > upper:
            continue
        events.append({
            "name": name, "name_zh": name,
            "date_start": to_iso(start_dt), "date_end": to_iso(end_dt),
            "url": link, "source": "visitokinawa",
            "category": "", "stars": 0,
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
            events.append({
                "name": name_ja, "name_zh": "",
                "date_start": to_iso(start_dt), "date_end": to_iso(end_dt),
                "url": base + href, "source": "okinawastory",
                "category": "", "stars": 0,
            })

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
    html = HTML_TEMPLATE
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

    today_is = get_today_is_events()
    scraped  = merge([get_visitokinawa_events(), get_okinawastory_events()])
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
