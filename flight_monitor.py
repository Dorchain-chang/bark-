#!/usr/bin/env python3
"""
成都 → 北京大兴 低价机票监控
使用 Playwright 抓取 Google Flights 数据
无需注册任何 API，即开即用
"""

import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen

BARK_KEY = os.environ.get("BARK_KEY", "")
PRICE_LIMIT = 850  # 含税总价上限（元）
BJ = timezone(timedelta(hours=8))

# 🎯 目标日期（你要飞的日期）
TARGET_DATES = ["2026-07-23", "2026-07-24"]

# ⏰ 监控截止日期（过了这天不再推送）
MONITOR_UNTIL = "2026-07-20"

# 路线：成都双流/天府 → 北京大兴
ROUTES = [
    ("CTU", "PKX", "双流"),
    ("TFU", "PKX", "天府"),
]


def send_bark(title: str, body: str) -> bool:
    if not BARK_KEY:
        return False
    print(f"\n📱 推送中: {title}")
    payload = json.dumps({
        "device_key": BARK_KEY, "title": title, "body": body,
        "group": "低价机票", "sound": "birdsong", "isArchive": 1,
    }).encode("utf-8")
    req = Request("https://api.day.app/push", data=payload,
                  headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urlopen(req, timeout=10) as resp:
            r = json.loads(resp.read())
            if r.get("code") == 200:
                print("  ✅ 推送成功！")
                return True
            else:
                print(f"  ❌ {r}")
                return False
    except Exception as e:
        print(f"  ❌ {e}")
        return False


def parse_google_flights_date(date_str: str) -> str:
    """把 YYYY-MM-DD 转成 Google Flights URL 用的格式"""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return d.strftime("%Y-%m-%d")


def search_via_playwright(origin: str, dest: str, date: str, origin_label: str) -> list:
    """用 Playwright 打开 Google Flights 抓取航班数据"""
    from playwright.sync_api import sync_playwright

    url = (
        f"https://www.google.com/travel/flights?"
        f"q=Flights+to+{dest}+from+{origin}+on+{date}"
    )
    print(f"  🌐 打开 {origin}({origin_label})→{dest}  {date}")

    flights = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(20000)

        try:
            page.goto(url, wait_until="domcontentloaded")
            # 等待搜索结果出现
            page.wait_for_selector('div[role="list"]', timeout=25000)
            page.wait_for_timeout(3000)  # 等价格加载

            # 获取页面所有航班卡片
            cards = page.query_selector_all('div[role="list"] > div, li[role="listitem"]')
            if not cards:
                # 备用选择器
                cards = page.query_selector_all('[class*="flight"], [class*="result"]')

            print(f"     找到 {len(cards)} 个航班卡片")

            for card in cards[:10]:
                text = card.inner_text()
                # 提取价格 ¥1234 或 ¥1,234
                prices = re.findall(r'[¥￥]\s*([\d,]+)', text)
                if not prices:
                    continue
                price = int(prices[0].replace(",", ""))
                if price > PRICE_LIMIT * 2:
                    continue  # 太贵忽略
                # 提取航司和时间
                lines = text.strip().split("\n")
                # 取前几行作为描述
                desc = " · ".join(l for l in lines[:6] if l.strip())[:200]
                flights.append({
                    "origin_label": origin_label,
                    "price": price,
                    "desc": desc,
                    "raw": text[:300],
                })

        except Exception as e:
            print(f"     ⚠️ 抓取出错: {e}")
            # 保存页面源码以便调试
            try:
                html = page.content()
                with open(f"debug_{origin}_{dest}.html", "w", encoding="utf-8") as f:
                    f.write(html[:50000])
                print(f"     💾 已保存调试文件 debug_{origin}_{dest}.html")
            except:
                pass

        finally:
            browser.close()

    return flights


def search_via_api(origin: str, dest: str, date: str, origin_label: str) -> list:
    """备用方案：用 requests 直接查"""

    # Try Skyscanner API
    try:
        import urllib.request
        api_url = (
            f"https://www.skyscanner.net/transport/flights/{origin.lower()}/"
            f"{dest.lower()}/{datetime.strptime(date, '%Y-%m-%d').strftime('%y%m%d')}/"
        )
        req = urllib.request.Request(api_url, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            prices = re.findall(r'[£¥$€]\s*([\d,]+)', html)
            print(f"     原始HTML: {len(html)}b, 找到价格: {prices[:10]}")
    except Exception as e:
        print(f"     ⚠️ 备用API失败: {e}")

    return []


def find_cheap_flights() -> list:
    """查目标日期所有低价航班"""
    now = datetime.now(BJ)
    print(f"📅 北京时间: {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"🎯 目标日期: {', '.join(TARGET_DATES)}")
    print(f"💰 上限: ¥{PRICE_LIMIT}（含税）")
    print()

    all_cheap = []

    for date in TARGET_DATES:
        print(f"\n═══ {date} ═══")
        for origin, dest, label in ROUTES:
            print(f"\n--- {label}机场 → 大兴 ---")
            try:
                flights = search_via_playwright(origin, dest, date, label)
            except Exception as e:
                print(f"  ❌ Playwright 失败: {e}")
                flights = []

            cheap = [f for f in flights if f["price"] <= PRICE_LIMIT]
        all_cheap.extend(cheap)

        if cheap:
            for f in cheap:
                print(f"  ✅ ¥{f['price']}  {f['desc'][:80]}")
        elif flights:
            prices = [f["price"] for f in flights]
            print(f"  😴 最低 ¥{min(prices)}，都超限")
        else:
            print(f"  📭 未抓到航班数据")

    all_cheap.sort(key=lambda f: f["price"])
    return all_cheap


def format_flights(flights: list) -> str:
    if not flights:
        return ""
    dates_str = ", ".join(d[5:] for d in TARGET_DATES)
    lines = [f"✈️ 成都→北京大兴 {dates_str} 低价", "─" * 25]
    for f in flights:
        lines.append(f"\n💵 ¥{f['price']} | {f['origin_label']}")
        lines.append(f"   {f['desc'][:100]}")
    lines.append(f"\n📌 共 {len(flights)} 个航班 ≤ ¥{PRICE_LIMIT}")
    return "\n".join(lines)


def main():
    print("=" * 40)
    print(f"✈️ 成都→北京大兴 低价监控")
    print(f"🎯 {', '.join(TARGET_DATES)}")
    print(f"⏰ 监控截止: {MONITOR_UNTIL}")
    print("=" * 40)

    if not BARK_KEY:
        print("\n❌ BARK_KEY 未配置")
        return

    # 检查是否过了监控截止日
    today = datetime.now(BJ).strftime("%Y-%m-%d")
    if today > MONITOR_UNTIL:
        print(f"\n📅 今天 {today}，已过监控截止日 {MONITOR_UNTIL}")
        print("✅ 监控任务结束！")
        body = (
            f"7月23-24日 成都→北京大兴 监控已结束\n"
            f"祝旅途愉快 ✈️🎉"
        )
        send_bark("✈️ 机票监控已结束", body)
        return

    flights = find_cheap_flights()
    print()

    if not flights:
        body = (
            f"7月23-24日 成都→北京大兴\n"
            f"未找到低于 ¥{PRICE_LIMIT} 的航班\n"
            f"下次继续关注 ✈️"
        )
        send_bark("✈️ 今日无特价机票", body)
        return

    body = format_flights(flights)
    best = min(f["price"] for f in flights)
    title = f"✈️ 成都→北京 最低¥{best}（7/23-24）"

    print(f"\n📋 推送内容:\n{body}")
    send_bark(title, body)
    print("\n✅ 完成！")


if __name__ == "__main__":
    main()
