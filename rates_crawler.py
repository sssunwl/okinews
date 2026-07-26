#!/usr/bin/env python3
"""每日抓一次日圓對台幣／港幣／美金／人民幣的參考匯率，寫進 docs/rates.json。

免金鑰的 open.er-api.com，抓失敗就保留上一版，不讓小工具在網站上壞掉或消失。
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).parent
RATES_FILE = ROOT / "docs" / "rates.json"
JST = timezone(timedelta(hours=9))
CURRENCIES = ["TWD", "HKD", "USD", "CNY", "KRW"]


def main():
    try:
        res = requests.get("https://open.er-api.com/v6/latest/JPY", timeout=15)
        res.raise_for_status()
        data = res.json()
        if data.get("result") != "success":
            raise ValueError("API 回傳 result != success")
        rates = data.get("rates", {})
        missing = [c for c in CURRENCIES if c not in rates]
        if missing:
            raise ValueError("缺少幣別：{}".format(missing))
    except (requests.RequestException, ValueError) as error:
        print("⚠️ 匯率抓取失敗（{}），保留上一版".format(error))
        return

    output = {
        "base": "JPY",
        "updated": datetime.now(JST).strftime("%Y-%m-%d %H:%M"),
        "rates": {code: rates[code] for code in CURRENCIES},
    }
    RATES_FILE.parent.mkdir(parents=True, exist_ok=True)
    RATES_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print("💱 匯率更新完成：1 日圓 = {} 台幣".format(output["rates"]["TWD"]))


if __name__ == "__main__":
    main()
