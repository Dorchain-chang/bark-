#!/usr/bin/env python3
"""
成都 → 北京大兴 低价机票监控
每日查询未来 7 天航班，总价 ≤ ¥750（含机建燃油）时推送到 iPhone
"""

import json
import os
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.error import URLError

# ============================================================
# 配置
# ============================================================
BARK_KEY = os.environ.get("BARK_KEY", "")
AMADEUS_KEY = os.environ.get("AMADEUS_API_KEY", "")
AMADEUS_SECRET = os.environ.get("AMADEUS_API_SECRET", "")
PRICE_LIMIT = 750  # 含税总价上限（人民币）
BJ = timezone(timedelta(hours=8))  # 北京时间

# 查询路线：成都两个机场 → 北京大兴
ROUTES = [
    ("CTU", "PKX"),  # 成都双流 → 北京大兴
    ("TFU", "PKX"),  # 成都天府 → 北京大兴
]


# ============================================================
# Amadeus API 工具
# ============================================================

def get_amadeus_token() -> str:
    """用 API Key + Secret 获取 Bearer Token"""
    import base64
    creds = f"{AMADEUS_KEY}:{AMADEUS_SECRET}"
    auth = base64.b64encode(creds.encode()).decode()

    req = Request(
        "https://test.api.amadeus.com/v1/security/oauth2/token",
        data=b"grant_type=client_credentials",
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read().decode())
        return result["access_token"]


def search_flights(origin: str, dest: str, date: str, token: str) -> list:
    """查询某天某航线的航班"""
    url = (
        f"https://test.api.amadeus.com/v2/shopping/flight-offers"
        f"?originLocationCode={origin}"
        f"&destinationLocationCode={dest}"
        f"&departureDate={date}"
        f"&adults=1"
        f"&currencyCode=CNY"
        f"&max=10"
    )
    req = Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
            offers = data.get("data", [])
            # 解析为统一格式
            results = []
            for offer in offers:
                price = float(offer["price"]["grandTotal"])
                currency = offer["price"]["currency"]
                # 取第一段行程
                for itinerary in offer.get("itineraries", []):
                    segments = itinerary.get("segments", [])
                    if not segments:
                        continue
                    first = segments[0]
                    last = segments[-1]
                    results.append({
                        "airline": first.get("carrierCode", ""),
                        "flight_number": first.get("number", ""),
                        "departure": f"{first['departure']['iataCode']} {first['departure']['at'][:16].replace('T', ' ')}",
                        "arrival": f"{last['arrival']['iataCode']} {last['arrival']['at'][:16].replace('T', ' ')}",
                        "duration": itinerary.get("duration", "").replace("PT", "").replace("H", "h ").replace("M", "m"),
                        "stops": len(segments) - 1,
                        "price": price,
                        "currency": currency,
                        "price_cny": price if currency == "CNY" else None,
                    })
            return results
    except URLError as e:
        print(f"  ⚠️ 请求失败 [{origin}→{dest} {date}]: {e}")
        # 尝试读取错误详情
        try:
            err_body = json.loads(e.read().decode()) if hasattr(e, 'read') else {}
            print(f"     错误详情: {json.dumps(err_body, ensure_ascii=False)[:500]}")
        except:
            pass
        return []
    except json.JSONDecodeError:
        print(f"  ⚠️ 解析失败 [{origin}→{dest} {date}]")
        return []


# ============================================================
# 核心：查未来 N 天的低价航班
# ============================================================

def find_cheap_flights(days_ahead: int = 7) -> list:
    """查询未来 days_ahead 天内所有低价航班"""
    now = datetime.now(BJ)
    print(f"📅 北京时间: {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"🔍 搜索未来 {days_ahead} 天 成都→北京大兴 的航班")
    print(f"💰 价格上限: ¥{PRICE_LIMIT}（含税）")

    # 获取 Token
    print("\n🔑 获取 Amadeus Token...")
    try:
        token = get_amadeus_token()
        print("  ✅ Token 获取成功")
    except Exception as e:
        print(f"  ❌ Token 获取失败: {e}")
        print("  💡 请检查 AMADEUS_API_KEY 和 AMADEUS_API_SECRET 是否正确")
        return []

    cheap_flights = []

    # 逐天逐路线查询
    for day_offset in range(days_ahead):
        date = (now + timedelta(days=day_offset)).strftime("%Y-%m-%d")
        for origin, dest in ROUTES:
            print(f"\n  📡 {date} {origin}→{dest} ...", end=" ", flush=True)
            flights = search_flights(origin, dest, date, token)

            cheap = [f for f in flights if f["price_cny"] and f["price_cny"] <= PRICE_LIMIT]
            if cheap:
                print(f"✅ 找到 {len(cheap)} 个低价航班！")
                cheap_flights.extend(cheap)
                for f in cheap:
                    print(f"     💰 ¥{f['price_cny']} | {f['airline']}{f['flight_number']} | "
                          f"{f['departure']} → {f['arrival']}")
            elif flights:
                prices = [f"{f['price_cny']}¥" for f in flights if f['price_cny']]
                print(f"😴 最低 ¥{min(f['price_cny'] for f in flights if f['price_cny'])}")
            else:
                print("📭 无数据")

    # 按价格排序
    cheap_flights.sort(key=lambda f: f["price_cny"] or 9999)

    print(f"\n📊 共找到 {len(cheap_flights)} 个低价航班（≤ ¥{PRICE_LIMIT}）")
    return cheap_flights


# ============================================================
# 格式化推送内容
# ============================================================

def format_flights(flights: list) -> str:
    """格式化航班信息为推送文案"""
    if not flights:
        return ""

    now = datetime.now(BJ)
    lines = [f"✈️ 成都→北京 低价机票 ({now.strftime('%m/%d')})", "─" * 20]

    for f in flights:
        price_str = f"¥{f['price_cny']}"
        line = f"\n💵 {price_str} | {f['airline']} {f['flight_number']}"
        lines.append(line)

        # 出发/到达
        dep = f['departure'].replace(' ', '  ')
        arr = f['arrival'].replace(' ', '  ')
        lines.append(f"   🛫 {dep}")
        lines.append(f"   🛬 {arr}")
        lines.append(f"   ⏱ {f['duration']} | 经停 {f['stops']} 次")

    lines.append(f"\n📌 共 {len(flights)} 个航班 ≤ ¥{PRICE_LIMIT}")
    return "\n".join(lines)


# ============================================================
# Bark 推送
# ============================================================

def send_bark(title: str, body: str) -> bool:
    if not BARK_KEY:
        print("\n❌ BARK_KEY 未设置")
        return False

    print(f"\n📱 推送中: {title}")
    payload = json.dumps({
        "device_key": BARK_KEY,
        "title": title,
        "body": body,
        "group": "低价机票",
        "sound": "birdsong",
        "icon": "https://img.icons8.com/fluency/48/airplane-take-off.png",
        "isArchive": 1,
    }).encode("utf-8")

    req = Request(
        "https://api.day.app/push",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("code") == 200:
                print(f"  ✅ 推送成功！")
                return True
            else:
                print(f"  ❌ {result}")
                return False
    except Exception as e:
        print(f"  ❌ {e}")
        return False


# ============================================================
# 主入口
# ============================================================

def main():
    print("=" * 40)
    print("✈️ 成都→北京 低价机票监控")
    print("=" * 40)

    # 检查配置
    if not AMADEUS_KEY or not AMADEUS_SECRET:
        print("\n❌ Amadeus API 未配置")
        print("   请在 GitHub → Settings → Secrets → Actions 添加：")
        print("   - AMADEUS_API_KEY")
        print("   - AMADEUS_API_SECRET")
        print("\n   注册地址: https://developers.amadeus.com/register")
        return

    if not BARK_KEY:
        print("\n❌ BARK_KEY 未配置")
        return

    # 查低价航班
    flights = find_cheap_flights(days_ahead=7)
    print()

    if not flights:
        print(f"😴 未来 7 天没有低于 ¥{PRICE_LIMIT} 的航班，不推送")
        # 可选：无论有没有都推送一条摘要，让用户知道脚本跑成功了
        body = f"未来 7 天 成都→北京大兴\n最低票价均超过 ¥{PRICE_LIMIT}\n暂无特价，下次继续关注 ✈️"
        send_bark("✈️ 今日无特价机票", body)
        return

    # 有低价航班 → 推送
    body = format_flights(flights)
    best_price = min(f["price_cny"] for f in flights if f["price_cny"])
    date_str = datetime.now(BJ).strftime("%m/%d")
    title = f"✈️ 成都→北京 最低¥{best_price} ！"

    print(f"\n📋 推送内容:\n{body}")
    send_bark(title, body)
    print("\n✅ 完成！")


if __name__ == "__main__":
    main()
