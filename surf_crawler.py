#!/usr/bin/env python3
"""三個沖繩衝浪點的即時風向風力、湧浪高度／週期、潮位，寫進 docs/surf-conditions.json。

跟 ocean_crawler.py（岸潛版）用同一組免金鑰資料源（open-meteo），但判斷邏輯完全不同：
潛水要的是「風平浪靜」，衝浪要的是「有湧浪、風要離岸（offshore）讓浪面乾淨」。
一樣不是「能不能下水」的權威判斷，網站上會清楚標示只是參考，實際永遠以現場、
教練與官方公告為準。
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).parent
OUTPUT_FILE = ROOT / "docs" / "surf-conditions.json"
JST = timezone(timedelta(hours=9))
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

TIMELINE_HOURS = ["06", "08", "10", "12", "14", "16", "18", "20", "22", "00"]

GENERAL_CAUTION = (
    "沖繩多數浪點是礁盤 reef break，干潮時礁石會外露，浪大時更容易割傷擦傷；"
    "離岸流、突然變大的湧浪、閃電雷雨一律先上岸。新手不建議在浪超過腰高或有經驗者"
    "都收板的時段還硬下水。"
)

# 湧浪高度門檻（公尺）：以下太平、以上偏大只適合有經驗的人。
SWELL_FLAT = 0.4
SWELL_BIG = 2.0
# 湧浪週期（秒）：越長代表浪越乾淨有力，短週期通常是風浪、雜亂。
PERIOD_WEAK = 8
# 潮位（公尺）：低於這個高度，多數礁盤浪點會開始外露見底。
TIDE_REEF_LOW = 0.5

SPOTS = [
    {
        "slug": "sunabe-surf",
        "name": "砂邊 Sunabe Surf Point",
        "region": "中部・北谷",
        "lat": 26.3179,
        "lon": 127.7552,
        "kind": "礁盤浪點・沙灘旁，多個 peak",
        # 面西開闊礁盤，東到東南風時浪面最乾淨；西到西北風會把浪面吹亂，
        # 而且這片海域跟岸潛/夜潛的人共用，浪大時尤其要留意水中其他人。
        "offshore_wind": [(45, 135)],
        "onshore_wind": [(255, 345)],
        "note": "面西開闊礁盤，多個 peak，跟砂邊岸潛區域共用海域；浪大時留意水裡有沒有潛水的人。",
        "reference_url": "https://www.windy.com/?waves,26.3179,127.7552,11",
    },
    {
        "slug": "maeda-surf",
        "name": "真栄田 Cape Maeda Surf Point",
        "region": "中部・恩納村",
        "lat": 26.5057,
        "lon": 127.8783,
        "kind": "礁盤浪點・岬角地形，浪大偏進階",
        # 跟青の洞窟同一個岬角，東南到南風是離岸；跟浮潛旺季重疊，
        # 浪起來時容易跟浮潛船、潛水員的活動範圍打架，要互相留意。
        "offshore_wind": [(120, 200)],
        "onshore_wind": [(280, 340)],
        "note": "跟青の洞窟浮潛區同一個岬角，浪起來時請跟浮潛船、潛水員保持距離。",
        "reference_url": "https://www.windy.com/?waves,26.5057,127.8783,11",
    },
    {
        "slug": "zanpa-surf",
        "name": "殘波岬 Cape Zanpa Surf Point",
        "region": "中部・讀谷",
        "lat": 26.4332,
        "lon": 127.7108,
        "kind": "礁盤浪點・岬角地形，離岸流常見，偏進階",
        # 讀谷最西側的岬角，同樣面西開闊；地形上岬角兩側容易形成離岸流，
        # 加上礁盤範圍大、干潮外露面積也大，新手不建議。
        "offshore_wind": [(45, 135)],
        "onshore_wind": [(255, 345)],
        "note": "岬角地形離岸流常見，礁盤範圍大、干潮外露面積也大，新手不建議、務必結伴。",
        "reference_url": "https://www.windy.com/?waves,26.4332,127.7108,11",
    },
]


def wind_dir_label(deg):
    labels = ["北", "北北東", "東北", "東北東", "東", "東南東", "東南", "南南東",
              "南", "南南西", "西南", "西南西", "西", "西北西", "西北", "北北西"]
    return labels[round(deg / 22.5) % 16]


def in_range(deg, ranges):
    for lo, hi in ranges:
        if lo <= deg <= hi:
            return True
    return False


def wind_exposure(spot, deg):
    if in_range(deg, spot["offshore_wind"]):
        return "offshore"
    if in_range(deg, spot["onshore_wind"]):
        return "onshore"
    return "neutral"


def fetch_wind(lat, lon):
    params = {
        "latitude": lat, "longitude": lon, "timezone": "Asia/Tokyo",
        "wind_speed_unit": "kn", "forecast_days": 2,
        "hourly": "wind_speed_10m,wind_direction_10m,wind_gusts_10m",
    }
    res = requests.get("https://api.open-meteo.com/v1/forecast", params=params,
                        headers=HEADERS, timeout=15)
    res.raise_for_status()
    return res.json()["hourly"]


def fetch_marine(lat, lon):
    params = {
        "latitude": lat, "longitude": lon, "timezone": "Asia/Tokyo", "forecast_days": 2,
        "hourly": "wave_height,wave_direction,swell_wave_height,swell_wave_period,sea_level_height_msl",
    }
    res = requests.get("https://marine-api.open-meteo.com/v1/marine", params=params,
                        headers=HEADERS, timeout=15)
    res.raise_for_status()
    return res.json()["hourly"]


def nearest_index(times, now):
    now_str = now.strftime("%Y-%m-%dT%H:00")
    if now_str in times:
        return times.index(now_str)
    target = now.replace(minute=0, second=0, microsecond=0)
    best_i, best_diff = 0, None
    for i, t in enumerate(times):
        try:
            dt = datetime.strptime(t, "%Y-%m-%dT%H:%M")
        except ValueError:
            continue
        diff = abs((dt - target.replace(tzinfo=None)).total_seconds())
        if best_diff is None or diff < best_diff:
            best_i, best_diff = i, diff
    return best_i


def find_tide_turn(sea_levels, times, index):
    turns = []
    for i in range(1, len(sea_levels) - 1):
        prev, cur, nxt = sea_levels[i - 1], sea_levels[i], sea_levels[i + 1]
        if cur >= prev and cur >= nxt:
            turns.append((i, "high"))
        elif cur <= prev and cur <= nxt:
            turns.append((i, "low"))
    if not turns:
        return None
    closest = min(turns, key=lambda pair: abs(pair[0] - index))
    hours_away = closest[0] - index
    kind = "滿潮" if closest[1] == "high" else "干潮"
    try:
        time_label = datetime.strptime(times[closest[0]], "%Y-%m-%dT%H:%M").strftime("%H:%M")
    except (ValueError, IndexError):
        time_label = ""
    return {"kind": kind, "time": time_label, "hours_away": hours_away}


def build_verdict(spot, wind_speed, wind_deg, swell_height, swell_period, tide):
    exposure = wind_exposure(spot, wind_deg)
    reasons = []

    reef_low = tide < TIDE_REEF_LOW
    too_onshore_and_big = exposure == "onshore" and swell_height > SWELL_BIG

    if swell_height < SWELL_FLAT:
        level = "avoid"
        reasons.append("湧浪只有 {:.1f} 公尺，太平沒什麼浪".format(swell_height))
    elif too_onshore_and_big:
        level = "avoid"
        reasons.append("湧浪 {:.1f} 公尺偏大，風又是頂頭浪（onshore），浪況會很亂".format(swell_height))
    elif swell_height > SWELL_BIG:
        level = "caution"
        reasons.append("湧浪 {:.1f} 公尺偏大，只適合有經驗的人".format(swell_height))
    elif exposure == "onshore":
        level = "caution"
        reasons.append("目前風向對這個點是頂頭浪，浪面會比較亂")
    elif swell_period < PERIOD_WEAK:
        level = "caution"
        reasons.append("週期只有 {:.0f} 秒，比較像風浪，浪型不會太乾淨".format(swell_period))
    else:
        level = "good"
        reasons.append("湧浪 {:.1f} 公尺、週期 {:.0f} 秒，浪況算不錯".format(swell_height, swell_period))
        if exposure == "offshore":
            reasons.append("風向對這個點是離岸風，浪面會比較乾淨")

    if reef_low:
        reasons.append("目前潮位偏低，礁盤可能外露，下水／走位要注意腳下")

    labels = {"good": "適合衝浪", "caution": "需留意", "avoid": "不建議下水"}
    return level, labels[level], "；".join(reasons)


def hour_datetime(now, hour_label):
    """把「06」「00」這種鐘點標籤換成下一次會發生的 JST 時間點——
    如果那個鐘點今天已經過了，就換算成明天同一鐘點，確保永遠是還沒到的時段。"""
    hh = int(hour_label)
    candidate = datetime(now.year, now.month, now.day, hh, 0, tzinfo=JST)
    if candidate < now:
        candidate += timedelta(days=1)
    return candidate


def closest_timeline_hour(now):
    return min(
        TIMELINE_HOURS,
        key=lambda h: min(abs(int(h) - now.hour), 24 - abs(int(h) - now.hour)),
    )


def build_timeline(spot, wind, marine, now):
    points = []
    for hour_label in TIMELINE_HOURS:
        target = hour_datetime(now, hour_label)
        wi = nearest_index(wind["time"], target)
        mi = nearest_index(marine["time"], target)

        wind_speed = wind["wind_speed_10m"][wi]
        wind_deg = wind["wind_direction_10m"][wi]
        swell_height = marine["swell_wave_height"][mi]
        swell_period = marine["swell_wave_period"][mi]
        sea_level = marine["sea_level_height_msl"][mi]

        level, label, reason = build_verdict(spot, wind_speed, wind_deg, swell_height, swell_period, sea_level)

        points.append({
            "hour": hour_label,
            "is_tomorrow": target.date() != now.date(),
            "wind_speed_kn": round(wind_speed, 1),
            "wind_dir_label": wind_dir_label(wind_deg),
            "wave_height_m": round(swell_height, 2),
            "tide_m": round(sea_level, 2),
            "verdict": level,
            "verdict_label": label,
            "verdict_reason": reason,
        })
    return points


def build_spot(spot, now):
    wind = fetch_wind(spot["lat"], spot["lon"])
    marine = fetch_marine(spot["lat"], spot["lon"])

    wi = nearest_index(wind["time"], now)
    mi = nearest_index(marine["time"], now)

    wind_speed = wind["wind_speed_10m"][wi]
    wind_deg = wind["wind_direction_10m"][wi]
    wind_gust = wind["wind_gusts_10m"][wi]
    swell_height = marine["swell_wave_height"][mi]
    swell_period = marine["swell_wave_period"][mi]
    wave_height = marine["wave_height"][mi]
    sea_level = marine["sea_level_height_msl"][mi]

    trend = "上漲" if marine["sea_level_height_msl"][mi + 1] > sea_level else "下降"
    turn = find_tide_turn(marine["sea_level_height_msl"], marine["time"], mi)

    level, label, reason = build_verdict(spot, wind_speed, wind_deg, swell_height, swell_period, sea_level)
    timeline = build_timeline(spot, wind, marine, now)

    return {
        "slug": spot["slug"],
        "name": spot["name"],
        "region": spot["region"],
        "kind": spot["kind"],
        "exposure": spot["note"],
        "reference_url": spot["reference_url"],
        "timeline": timeline,
        "closest_timeline_hour": closest_timeline_hour(now),
        "wind_speed_kn": round(wind_speed, 1),
        "wind_gust_kn": round(wind_gust, 1),
        "wind_deg": round(wind_deg),
        "wind_dir_label": wind_dir_label(wind_deg),
        "wave_height_m": round(swell_height, 2),
        "swell_height_m": round(swell_height, 2),
        "swell_period_s": round(swell_period, 1),
        "sea_wave_height_m": round(wave_height, 2),
        "tide_m": round(sea_level, 2),
        "tide_trend": trend,
        "tide_turn": turn,
        "verdict": level,
        "verdict_label": label,
        "verdict_reason": reason,
    }


def main():
    now = datetime.now(JST)
    spots_out = []
    for spot in SPOTS:
        try:
            spots_out.append(build_spot(spot, now))
        except (requests.RequestException, KeyError, IndexError, ValueError) as error:
            print("⚠️ {} 抓取失敗（{}），略過這個點".format(spot["name"], error))

    if not spots_out:
        print("⚠️ 全部點都抓失敗，保留上一版")
        return

    output = {
        "updated": now.strftime("%Y-%m-%d %H:%M"),
        "general_caution": GENERAL_CAUTION,
        "spots": spots_out,
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print("🏄 浪況更新完成：{} 個點".format(len(spots_out)))


if __name__ == "__main__":
    main()
