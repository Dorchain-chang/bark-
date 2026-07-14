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


def search_via_playwright(origin: str, dest: str, date: str, origin_label: str) -> list:
    """用 Playwright + Stealth 抓取 Google Flights 航班数据"""
    from playwright.sync_api import sync_playwright

    url = (
        f"https://www.google.com/travel/flights?"
        f"q=Flights+to+{dest}+from+{origin}+on+{date}"
    )
    print(f"  🌐 打开 {origin}({origin_label})→{dest}  {date}")

    flights = []
    with sync_playwright() as p:
        # 用 Stealth 模式启动，防检测
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        page = context.new_page()

        try:
            # 注入 Stealth 补丁（反检测）
            try:
                from playwright_stealth import Stealth
                Stealth().apply_stealth_sync(page)
                print(f"     🕶️ Stealth 模式已启用")
            except ImportError:
                print(f"     ⚠️ Stealth 不可用，继续裸奔")

            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(5000)

            # 尝试多种方式找搜索结果
            selectors = [
                'div[role="list"]',
                '[data-g]',
                '.Rk10dc',      # Google Flights 卡片
                '.yR1fYc',      # 价格元素
                'li[role="listitem"]',
                '.gws-flights-results__result-item',
            ]
            found = False
            for sel in selectors:
                try:
                    el = page.wait_for_selector(sel, timeout=8000)
                    if el:
                        print(f"     ✅ 找到结果选择器: {sel}")
                        found = True
                        break
                except:
                    continue

            if not found:
                # 看看页面加载了啥
                title = page.title()
                print(f"     ⚠️ 未找到航班列表, 页面标题: {title}")
                # 可能是验证码或跳转
                page_content = page.content()
                if "captcha" in page_content.lower():
                    print(f"     🤖 触发了 Google 验证码!")
                return []

            page.wait_for_timeout(3000)

            # 抓取所有航班卡片文本
            content = page.inner_text("body")
            # 用正则找所有 ¥ 价格
            price_matches = re.findall(r'([¥￥])\s*([\d,]+)', content)
            if price_matches:
                for sym, price_str in price_matches:
                    try:
                        price = int(price_str.replace(",", ""))
                        if price <= PRICE_LIMIT:
                            # 找这个价格附近的文本描述
                            idx = content.find(f"{sym}{price_str}")
                            snippet = content[max(0, idx-200):idx+200]
                            flights.append({
                                "origin_label": origin_label,
                                "price": price,
                                "desc": snippet[:150].strip(),
                            })
                    except ValueError:
                        continue

            # 去重（按价格去重）
            seen_prices = set()
            unique = []
            for f in flights:
                if f["price"] not in seen_prices:
                    seen_prices.add(f["price"])
                    unique.append(f)
            flights = unique

            print(f"     找到 {len(price_matches)} 个价格标注, {len(flights)} 个不超过 ¥{PRICE_LIMIT}")

        except Exception as e:
            print(f"     ⚠️ 抓取出错: {e}")

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
