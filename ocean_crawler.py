#!/usr/bin/env python3
"""三個沖繩潛點的即時風向風力、浪高、潮汐，寫進 docs/ocean-conditions.json。

資料來源全部免金鑰：
- 風（風速／風向／陣風）：api.open-meteo.com 一般天氣預報
- 浪高／湧浪／潮位：marine-api.open-meteo.com 海洋預報

判斷規則是通用的潛水安全經驗法則（風速、浪高門檻）加上每個點自己的地形特性
（面向哪個方向、被什麼擋住），細節寫在 SPOTS 裡並附來源；這不是「可以下水」的
權威判斷，網站上會清楚標示只是參考，實際永遠以現場、教練與官方公告為準。
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).parent
OUTPUT_FILE = ROOT / "docs" / "ocean-conditions.json"
JST = timezone(timedelta(hours=9))
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# 風向角度（氣象學定義：風從哪個方向吹來）分類門檻。
WIND_SPEED_CALM = 7      # 節，以下：平穩
WIND_SPEED_MODERATE = 15  # 節，以下：需留意；以上：風浪較大
WAVE_CALM = 0.6           # 公尺，以下：平穩
WAVE_MODERATE = 1.0       # 公尺，以下：需留意；以上：不建議岸潛

SPOTS = [
    {
        "slug": "sunabe",
        "name": "砂邊2號點 Sunabe II",
        "region": "中部・北谷",
        "lat": 26.3179,
        "lon": 127.7552,
        "kind": "岸潛・夜潛熱門點",
        # 面西的岸潛點，開闊面對東海；東風／微風時最平穩，西到西北強風會直接揚湧上壁。
        "good_wind": [(45, 135)],
        "bad_wind": [(255, 345)],
        "exposure": "面向西側開闊海域，東風或微風最穩，西／西北強風會直接推浪上岸壁。",
        "reference_url": "https://windy.app/forecast2/spot/4013465/Sunabe+II",
    },
    {
        "slug": "cape-maeda",
        "name": "青の洞窟 Cape Maeda",
        "region": "中部・恩納村",
        "lat": 26.5057,
        "lon": 127.8783,
        "kind": "岬角浮潛・沿階梯下水",
        # 同樣是西側岬角地形，強西／西北風浪會讓階梯下水口變危險，官方會直接封閉。
        "good_wind": [(45, 135)],
        "bad_wind": [(255, 345)],
        "exposure": "岬角地形、沿階梯下水，強西／西北風浪會使入水口變得危險，現場有官方旗幟與即時影像可查。",
        "reference_url": "https://windy.app/forecast2/spot/8519891/Cape+Maeda+Blue+Cave",
        "official_note": "真栄田岬official網站有即時影像與旗幟燈號（藍=可下水／黃=僅隨教練／紅=禁止），以現場公告為準。",
    },
    {
        "slug": "gorilla-chop",
        "name": "大猩猩 Gorilla Chop",
        "region": "北部・本部",
        "lat": 26.6975,
        "lon": 127.8672,
        "kind": "岸潛・浮潛，適合初學",
        # 本部半島南岸，北側有山地擋風，是全島少數「北風越強越穩」的岸潛點；
        # 換季後（5-10月南風季）南風一大反而是這裡最容易出局的時候。
        "good_wind": [(315, 360), (0, 45)],
        "bad_wind": [(135, 225)],
        "exposure": "本部半島南岸，北側有山擋風，是全島少數北風越強越穩的岸潛點；5-10月南風季吹南風時反而最容易停潛。",
        "reference_url": "https://windy.app/forecast2/spot/5967071/Gorilla+Chop",
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
    if in_range(deg, spot["good_wind"]):
        return "favorable"
    if in_range(deg, spot["bad_wind"]):
        return "unfavorable"
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
    # 沒有精確吻合就找最接近的
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
    """找離現在最近的滿潮／干潮時間點（簡單抓局部極值）。"""
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


def build_verdict(spot, wind_speed, wind_deg, wave_height):
    exposure = wind_exposure(spot, wind_deg)
    reasons = []

    if wind_speed > WIND_SPEED_MODERATE or wave_height > WAVE_MODERATE:
        level = "avoid"
        if wind_speed > WIND_SPEED_MODERATE:
            reasons.append("風速 {:.0f} 節偏強".format(wind_speed))
        if wave_height > WAVE_MODERATE:
            reasons.append("浪高 {:.1f} 公尺偏大".format(wave_height))
    elif wind_speed > WIND_SPEED_CALM or wave_height > WAVE_CALM or exposure == "unfavorable":
        level = "caution"
        if wind_speed > WIND_SPEED_CALM:
            reasons.append("風速 {:.0f} 節，有點感覺".format(wind_speed))
        if wave_height > WAVE_CALM:
            reasons.append("浪高 {:.1f} 公尺，比平常大".format(wave_height))
        if exposure == "unfavorable":
            reasons.append("目前風向對這個點是受風側")
    else:
        level = "good"
        reasons.append("風速浪高都在平穩範圍")
        if exposure == "favorable":
            reasons.append("風向對這個點是背風側，理論上更穩")

    labels = {"good": "看起來平穩", "caution": "需留意", "avoid": "不建議岸潛"}
    return level, labels[level], "；".join(reasons)


def build_spot(spot, now):
    wind = fetch_wind(spot["lat"], spot["lon"])
    marine = fetch_marine(spot["lat"], spot["lon"])

    wi = nearest_index(wind["time"], now)
    mi = nearest_index(marine["time"], now)

    wind_speed = wind["wind_speed_10m"][wi]
    wind_deg = wind["wind_direction_10m"][wi]
    wind_gust = wind["wind_gusts_10m"][wi]
    wave_height = marine["wave_height"][mi]
    swell_height = marine["swell_wave_height"][mi]
    swell_period = marine["swell_wave_period"][mi]
    sea_level = marine["sea_level_height_msl"][mi]

    trend = "上漲" if marine["sea_level_height_msl"][mi + 1] > sea_level else "下降"
    turn = find_tide_turn(marine["sea_level_height_msl"], marine["time"], mi)

    level, label, reason = build_verdict(spot, wind_speed, wind_deg, wave_height)

    return {
        "slug": spot["slug"],
        "name": spot["name"],
        "region": spot["region"],
        "kind": spot["kind"],
        "exposure": spot["exposure"],
        "official_note": spot.get("official_note", ""),
        "reference_url": spot["reference_url"],
        "wind_speed_kn": round(wind_speed, 1),
        "wind_gust_kn": round(wind_gust, 1),
        "wind_deg": round(wind_deg),
        "wind_dir_label": wind_dir_label(wind_deg),
        "wave_height_m": round(wave_height, 2),
        "swell_height_m": round(swell_height, 2),
        "swell_period_s": round(swell_period, 1),
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
        "spots": spots_out,
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print("🌊 海況更新完成：{} 個點".format(len(spots_out)))


if __name__ == "__main__":
    main()
