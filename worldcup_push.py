#!/usr/bin/env python3
"""
World Cup 2026 推送脚本
每天早上 8:00 推送当天赛程，晚上 21:00 推送比赛结果
通过 Bark App 推送到 iPhone
"""

import json
import os
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# ============================================================
# 配置
# ============================================================
BARK_KEY = os.environ.get("BARK_KEY", "")
TZ_OFFSET = timedelta(hours=8)  # 北京时间


# ============================================================
# 数据源
# ============================================================
WORLDCUP26_API = "https://worldcup26.ir/get/games"
ESPN_API = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"


def fetch_json(url: str, timeout: int = 15) -> Optional[dict]:
    """获取 JSON 数据，失败返回 None"""
    try:
        req = Request(url, headers={
            "User-Agent": "WorldCupPush/1.0",
            "Accept": "application/json",
        })
        with urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)
    except (URLError, HTTPError, json.JSONDecodeError, OSError) as e:
        print(f"  ❌ 请求失败 [{url}]: {e}")
        return None


# ============================================================
# 解析 worldcup26.ir（主数据源）
# ============================================================

def to_score(val) -> Optional[int]:
    """把分数转成 int，处理 'null' 字符串和 None"""
    if val is None:
        return None
    s = str(val).strip().lower()
    if s in ("null", "none", "", "?"):
        return None
    try:
        return int(float(s))  # 先转 float 再 int，防止 "2.0" 之类
    except (ValueError, TypeError):
        return None


def to_status(finished: Optional[str], time_elapsed: Optional[str]) -> str:
    """转换比赛状态"""
    # time_elapsed 的可能值: "finished", "not_started", "in_progress" 或类似
    te = (time_elapsed or "").strip().lower()
    if te in ("finished", "full_time", "completed", "final"):
        return "finished"
    if te in ("in_progress", "live", "first_half", "second_half", "half_time", "halftime"):
        return "live"
    if te in ("not_started", "scheduled", "pre", ""):
        return "scheduled"
    # 根据 finished 字段判断
    fn = (finished or "").strip().upper()
    if fn == "TRUE":
        return "finished"
    return "scheduled"


def parse_worldcup26_matches(data) -> Optional[list]:
    """解析 worldcup26.ir 的比赛数据"""
    try:
        games = None
        if isinstance(data, list):
            games = data
        elif isinstance(data, dict):
            # 实际返回: {"games": [...]}
            games = data.get("games") or data.get("data") or data.get("matches") or []

        if not games:
            return None

        parsed = []
        for m in games:
            if not isinstance(m, dict):
                continue

            home_team = m.get("home_team_name_en") or m.get("home_team") or "?"
            away_team = m.get("away_team_name_en") or m.get("away_team") or "?"
            home_score = to_score(m.get("home_score"))
            away_score = to_score(m.get("away_score"))
            status = to_status(m.get("finished"), m.get("time_elapsed"))

            # 时间: "06/11/2026 13:00" → 转成 HH:mm
            raw_time = str(m.get("local_date") or m.get("date") or "")
            time_display = raw_time[-5:] if len(raw_time) >= 5 else raw_time

            # 阶段: group + group_name
            group = m.get("group") or ""
            stage = f"Group {group}" if group else ""

            # 原始日期用于过滤
            date_str = raw_time[:10] if len(raw_time) >= 10 else ""  # "06/11/2026"

            parsed.append({
                "home_team": str(home_team),
                "away_team": str(away_team),
                "home_score": home_score,
                "away_score": away_score,
                "status": status,
                "time": time_display,
                "date_str": date_str,
                "stage": stage,
            })

        return parsed if parsed else None

    except Exception as e:
        print(f"  ⚠️ 解析 worldcup26.ir 数据出错: {e}")
        return None


# ============================================================
# 解析 ESPN（备用）
# ============================================================

ESPN_STATUS_MAP = {
    "status_scheduled": "scheduled",
    "status_in_progress": "live",
    "status_final": "finished",
    "status_postponed": "scheduled",
    "status_cancelled": "finished",
    "status_suspended": "live",
    "pre_game": "scheduled",
    "in_progress": "live",
    "half": "live",
    "final": "finished",
    "scheduled": "scheduled",
    "live": "live",
    "finished": "finished",
}


def parse_espn_matches(data) -> Optional[list]:
    """解析 ESPN 的比赛数据"""
    try:
        events = data.get("events", [])
        if not events:
            return None

        parsed = []
        for event in events:
            comps = event.get("competitions", [{}])
            if not comps:
                continue
            comp = comps[0]

            competitors = comp.get("competitors", [])
            if len(competitors) < 2:
                continue

            home = competitors[0]
            away = competitors[1]

            home_team = home.get("team", {}).get("displayName", "?")
            away_team = away.get("team", {}).get("displayName", "?")
            home_score = to_score(home.get("score"))
            away_score = to_score(away.get("score"))

            # ESPN 状态: "STATUS_SCHEDULED", "STATUS_IN_PROGRESS", "STATUS_FINAL"
            raw_status = comp.get("status", {}).get("type", {}).get("name", "scheduled")
            raw_status = raw_status.lower()
            status = ESPN_STATUS_MAP.get(raw_status, "scheduled")

            # ESPN 时间: ISO 8601 → 取 HH:mm
            date_str = comp.get("date") or event.get("date") or ""
            time_display = date_str[11:16] if len(date_str) >= 16 else date_str
            # 日期部分 YYYY-MM-DD
            iso_date = date_str[:10] if len(date_str) >= 10 else ""

            stage = event.get("name", "")
            # ESPN 的 name 可能是 "2026 FIFA World Cup | Group A"，截短
            if "|" in stage:
                stage = stage.split("|")[-1].strip()

            parsed.append({
                "home_team": str(home_team),
                "away_team": str(away_team),
                "home_score": home_score,
                "away_score": away_score,
                "status": status,
                "time": time_display,
                "date_str": iso_date,
                "stage": stage,
            })

        return parsed if parsed else None
    except Exception as e:
        print(f"  ⚠️ 解析 ESPN 数据出错: {e}")
        return None


# ============================================================
# 获取今天的比赛
# ============================================================

def today_matches() -> list:
    """获取今天的比赛"""
    now_beijing = datetime.now(timezone.utc) + TZ_OFFSET
    today_mmdd = now_beijing.strftime("%m/%d/%Y")  # "06/18/2026" (worldcup26.ir 格式)
    today_iso = now_beijing.strftime("%Y-%m-%d")    # "2026-06-18" (ESPN 格式)
    print(f"📅 北京时间: {now_beijing.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔍 匹配日期: {today_mmdd} 或 {today_iso}")

    all_today = []

    # --- 数据源 1: worldcup26.ir ---
    print("\n--- 数据源 1: worldcup26.ir ---")
    data = fetch_json(WORLDCUP26_API)
    if data:
        games = parse_worldcup26_matches(data)
        if games:
            print(f"  ✅ 解析到 {len(games)} 场比赛（全部）")
            for m in games:
                if today_mmdd in m["date_str"] or m["date_str"] in today_mmdd:
                    all_today.append(m)
                    print(f"     📅 {m['time']} {m['home_team']} vs {m['away_team']} [{m['status']}]")
            print(f"  📌 今日比赛: {sum(1 for m in games if today_mmdd in m['date_str'] or m['date_str'] in today_mmdd)} 场")
        else:
            print("  ⚠️ 解析失败")
    else:
        print("  ⚠️ 获取失败")

    # --- 数据源 2: ESPN (备用) ---
    if not all_today:
        print("\n--- 数据源 2: ESPN (备用) ---")
        data = fetch_json(ESPN_API)
        if data:
            games = parse_espn_matches(data)
            if games:
                print(f"  ✅ 解析到 {len(games)} 场比赛（全部）")
                for m in games:
                    if today_iso in m["date_str"] or m["date_str"] == "":
                        all_today.append(m)
                        print(f"     📅 {m['time']} {m['home_team']} vs {m['away_team']} [{m['status']}]")
                print(f"  📌 今日比赛: {len(all_today)} 场")

    # 去重
    seen = set()
    unique = []
    for m in all_today:
        key = (m["home_team"], m["away_team"])
        if key not in seen:
            seen.add(key)
            unique.append(m)

    print(f"\n📊 最终: {len(unique)} 场比赛")
    return unique


# ============================================================
# 格式化消息
# ============================================================

def format_schedule(matches: list) -> str:
    """早上：当天赛程"""
    if not matches:
        return "📅 世界杯 | 今天没有比赛，休息一天～"

    lines = []
    today = (datetime.now(timezone.utc) + TZ_OFFSET).strftime("%m/%d")
    lines.append(f"📅 世界杯 · {today} 赛程预告")
    lines.append("─" * 20)

    # 按时间分组
    upcoming = [m for m in matches if m["status"] == "scheduled"]
    live = [m for m in matches if m["status"] == "live"]
    finished = [m for m in matches if m["status"] == "finished"]

    if finished:
        lines.append(f"\n✅ 已结束 ({len(finished)}):")
        for m in finished:
            hs = m["home_score"] if m["home_score"] is not None else "?"
            as_ = m["away_score"] if m["away_score"] is not None else "?"
            emoji = " 👑" if (m["home_score"] is not None and m["away_score"] is not None
                              and m["home_score"] != m["away_score"]) else ""
            lines.append(f"  {m['home_team']} {hs} - {as_} {m['away_team']}{emoji}")

    if live:
        lines.append(f"\n⚡ 进行中 ({len(live)}):")
        for m in live:
            hs = m["home_score"] if m["home_score"] is not None else "?"
            as_ = m["away_score"] if m["away_score"] is not None else "?"
            lines.append(f"  🟢 {m['home_team']} {hs} - {as_} {m['away_team']}")

    if upcoming:
        lines.append(f"\n⏳ 赛程 ({len(upcoming)}):")
        for m in upcoming:
            s = f"  {m['time']} {m['home_team']} vs {m['away_team']}"
            if m["stage"]:
                s += f" ({m['stage']})"
            lines.append(s)

    lines.append("\n─── via WorldCup Push ───")
    return "\n".join(lines)


def format_results(matches: list) -> str:
    """晚上：当天战报"""
    if not matches:
        return "⚽ 世界杯 | 今天没有比赛"

    lines = []
    today = (datetime.now(timezone.utc) + TZ_OFFSET).strftime("%m/%d")
    lines.append(f"⚽ 世界杯 · {today} 战报")
    lines.append("─" * 20)

    finished = [m for m in matches if m["status"] == "finished"]
    live = [m for m in matches if m["status"] == "live"]
    upcoming = [m for m in matches if m["status"] == "scheduled"]

    if finished:
        lines.append(f"\n✅ 已结束 ({len(finished)}):")
        for m in finished:
            hs = m["home_score"] if m["home_score"] is not None else "?"
            as_ = m["away_score"] if m["away_score"] is not None else "?"
            line = f"  {m['home_team']} {hs} - {as_} {m['away_team']}"
            if m["home_score"] is not None and m["away_score"] is not None:
                if m["home_score"] > m["away_score"]:
                    line += " 👑"
                elif m["away_score"] > m["home_score"]:
                    line += " 👑"
                else:
                    line += " 🤝"
            if m["stage"]:
                line += f" ({m['stage']})"
            lines.append(line)

    if live:
        lines.append(f"\n⚡ 还在踢 ({len(live)}):")
        for m in live:
            hs = m["home_score"] if m["home_score"] is not None else "?"
            as_ = m["away_score"] if m["away_score"] is not None else "?"
            lines.append(f"  🟢 {m['home_team']} {hs} - {as_} {m['away_team']}")

    if upcoming:
        lines.append(f"\n⏳ 即将开始 ({len(upcoming)}):")
        for m in upcoming:
            s = f"  {m['time']} {m['home_team']} vs {m['away_team']}"
            if m["stage"]:
                s += f" ({m['stage']})"
            lines.append(s)

    lines.append("\n─── via WorldCup Push ───")
    return "\n".join(lines)


# ============================================================
# Bark 推送
# ============================================================

def send_bark(title: str, body: str, group: str = "世界杯") -> bool:
    """通过 Bark API 推送通知到 iPhone"""
    if not BARK_KEY:
        print("\n❌ 未设置 BARK_KEY 环境变量")
        print("💡 请在 GitHub → Settings → Secrets → Actions → 添加 BARK_KEY")
        print("   当前 BARK_KEY 长度:", len(os.environ.get("BARK_KEY", "")))
        return False

    print(f"\n📱 推送中...")
    print(f"   标题: {title}")
    print(f"   内容: {body[:200]}...")

    payload = json.dumps({
        "device_key": BARK_KEY,
        "title": title,
        "body": body,
        "group": group,
        "sound": "birdsong",
        "icon": "https://img.icons8.com/fluency/48/football2.png",
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
            code = result.get("code")
            if code == 200:
                print(f"  ✅ 推送成功！请查看手机 📱")
                return True
            else:
                print(f"  ❌ Bark API 返回错误: {result}")
                return False
    except Exception as e:
        print(f"  ❌ 推送失败: {e}")
        return False


# ============================================================
# 主入口
# ============================================================

def main():
    print("=" * 40)
    print("🌍 World Cup 2026 Push")
    print("=" * 40)

    raw_type = os.environ.get("PUSH_TYPE", "auto")
    # auto 模式：根据当前时间判断
    now_hour = (datetime.now(timezone.utc) + TZ_OFFSET).hour
    if raw_type == "auto":
        push_type = "morning" if now_hour < 15 else "evening"  # UTC+8 8:00=0UTC, 21:00=13UTC
    else:
        push_type = raw_type
    print(f"📋 推送类型: {'🌅 早间赛程' if push_type == 'morning' else '🌇 晚间战报'} ({raw_type})")
    print()

    matches = today_matches()
    print()

    if not matches:
        print("⚠️ 没有获取到比赛数据，仍发送通知")
        date_str = (datetime.now(timezone.utc) + TZ_OFFSET).strftime("%m/%d")
        if push_type == "morning":
            send_bark(f"📅 世界杯 · {date_str} 今日无赛程",
                      "今天没有世界杯比赛安排，休息一天～")
        else:
            send_bark(f"⚽ 世界杯 · {date_str} 今日无比赛",
                      "今天没有世界杯比赛，今晚好好休息！")
        return

    date_str = (datetime.now(timezone.utc) + TZ_OFFSET).strftime("%m/%d")

    if push_type == "morning":
        title = f"📅 世界杯赛程 · {date_str}"
        body = format_schedule(matches)
    else:
        title = f"⚽ 世界杯战报 · {date_str}"
        body = format_results(matches)

    print(f"📋 推送内容:\n{body}")
    send_bark(title, body)
    print("\n✅ 完成！")


if __name__ == "__main__":
    main()
