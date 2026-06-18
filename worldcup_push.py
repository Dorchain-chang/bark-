#!/usr/bin/env python3
"""
World Cup 2026 推送脚本
每天早上 8:00 推送当天赛程，晚上 21:00 推送比赛结果 + 进球球员
所有时间自动转换为北京时间
通过 Bark App 推送到 iPhone
"""

import json
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

BARK_KEY = os.environ.get("BARK_KEY", "")
BJ = timezone(timedelta(hours=8))  # 北京时间

# ============================================================
# 世界杯 16 个体育场 → 时区映射
# 2026 年 6-7 月: 美加实行夏令时, 墨西哥已取消夏令时
# ============================================================
STADIUM_TZ = {
    "1": -6,   # Estadio Azteca, Mexico City — Mexico (CST, no DST)
    "2": -6,   # Estadio Akron, Guadalajara — Mexico
    "3": -6,   # Estadio BBVA, Monterrey — Mexico
    "4": -5,   # AT&T Stadium, Dallas — US Central (CDT)
    "5": -5,   # NRG Stadium, Houston — US Central
    "6": -5,   # Arrowhead Stadium, Kansas City — US Central
    "7": -4,   # Mercedes-Benz Stadium, Atlanta — US Eastern (EDT)
    "8": -4,   # Hard Rock Stadium, Miami — US Eastern
    "9": -4,   # Gillette Stadium, Boston — US Eastern
    "10": -4,  # Lincoln Financial Field, Philadelphia — US Eastern
    "11": -4,  # MetLife Stadium, NY/NJ — US Eastern
    "12": -4,  # BMO Field, Toronto — Canada Eastern (EDT)
    "13": -7,  # BC Place, Vancouver — Canada Pacific (PDT)
    "14": -7,  # Lumen Field, Seattle — US Pacific (PDT)
    "15": -7,  # Levi's Stadium, San Francisco — US Pacific
    "16": -7,  # SoFi Stadium, Los Angeles — US Pacific
}
DEFAULT_TZ = -5  # 默认时区（US Central）


# ============================================================
# 工具函数
# ============================================================

def fetch_json(url: str, timeout: int = 15) -> Optional[dict]:
    try:
        req = Request(url, headers={
            "User-Agent": "WorldCupPush/1.0",
            "Accept": "application/json",
        })
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (URLError, HTTPError, json.JSONDecodeError, OSError) as e:
        print(f"  ❌ 请求失败: {e}")
        return None


def to_score(val) -> Optional[int]:
    if val is None:
        return None
    s = str(val).strip().lower()
    if s in ("null", "none", "", "?"):
        return None
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


def local_to_beijing(local_date_str: str, stadium_id: str) -> str:
    """
    把球场当地时间转成北京时间
    local_date_str: "06/11/2026 13:00" (MM/DD/YYYY HH:mm)
    返回: "06/11 03:00" (月/日 时:分)
    """
    try:
        local_dt = datetime.strptime(local_date_str.strip(), "%m/%d/%Y %H:%M")
        offset = STADIUM_TZ.get(stadium_id, DEFAULT_TZ)
        # 当地时间 → UTC → 北京时间
        utc_dt = local_dt.replace(tzinfo=timezone.utc) - timedelta(hours=offset)
        bj_dt = utc_dt.astimezone(BJ)
        return bj_dt.strftime("%m/%d %H:%M")
    except (ValueError, TypeError):
        return local_date_str[:16]  # 解析失败返回原样


def local_to_beijing_date(local_date_str: str, stadium_id: str) -> str:
    """返回北京时间的日期部分 (YYYY-MM-DD)"""
    try:
        local_dt = datetime.strptime(local_date_str.strip(), "%m/%d/%Y %H:%M")
        offset = STADIUM_TZ.get(stadium_id, DEFAULT_TZ)
        utc_dt = local_dt.replace(tzinfo=timezone.utc) - timedelta(hours=offset)
        bj_dt = utc_dt.astimezone(BJ)
        return bj_dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return ""


def parse_scorers(scorers_str) -> list:
    """解析进球球员字符串"""
    if not scorers_str or scorers_str.strip().lower() == "null":
        return []
    s = scorers_str.strip()
    # 替换花引号为直引号
    s = s.replace("“", '"').replace("”", '"')
    # 提取所有引号内容，包含分钟数
    # 匹配 "任意字符+数字+' 任意字符"
    matches = re.findall(r'"([^"]*?\d+\'[^"]*?)"', s)
    if matches:
        return [m.strip() for m in matches]
    # 如果正则失败，尝试简单清理
    s = s.strip("{}").strip()
    parts = [p.strip().strip("\"'") for p in s.split('","')]
    return [p for p in parts if p and p.lower() != "null"]


# ============================================================
# 数据源 1: worldcup26.ir（主）
# ============================================================

def parse_worldcup26_matches(data: dict) -> list:
    """解析并返回统一格式的比赛列表，时间已转北京时间"""
    raw_games = data.get("games") if isinstance(data, dict) else data
    if not raw_games:
        return []

    now = datetime.now(BJ)
    today_bj = now.strftime("%Y-%m-%d")

    parsed = []
    for m in raw_games:
        if not isinstance(m, dict):
            continue

        # 基本数据
        home_team = m.get("home_team_name_en", "?")
        away_team = m.get("away_team_name_en", "?")
        home_score = to_score(m.get("home_score"))
        away_score = to_score(m.get("away_score"))

        # 状态
        te = (m.get("time_elapsed") or "").strip().lower()
        if te in ("finished", "full_time", "completed", "final"):
            status = "finished"
        elif te in ("in_progress", "live", "first_half", "second_half", "half_time"):
            status = "live"
        else:
            fn = (m.get("finished") or "").strip().upper()
            status = "finished" if fn == "TRUE" else "scheduled"

        # 球场 ID & 时间
        stadium_id = str(m.get("stadium_id", ""))
        local_date = str(m.get("local_date", ""))
        bj_time = local_to_beijing(local_date, stadium_id)
        bj_date = local_to_beijing_date(local_date, stadium_id)

        # 阶段
        group = m.get("group", "")
        stage = f"Group {group}" if group else ""

        # 进球球员
        home_scorers = parse_scorers(m.get("home_scorers"))
        away_scorers = parse_scorers(m.get("away_scorers"))

        parsed.append({
            "home_team": home_team,
            "away_team": away_team,
            "home_score": home_score,
            "away_score": away_score,
            "status": status,
            "bj_time": bj_time,          # "06/18 03:00" 北京时间
            "bj_date": bj_date,           # "2026-06-18"
            "stage": stage,
            "home_scorers": home_scorers,
            "away_scorers": away_scorers,
        })

    return parsed


# ============================================================
# 数据源 2: ESPN（备用）
# ============================================================

ESPN_STATUS_MAP = {
    "status_scheduled": "scheduled", "status_in_progress": "live",
    "status_final": "finished", "status_postponed": "scheduled",
    "status_cancelled": "finished", "status_suspended": "live",
    "pre_game": "scheduled", "in_progress": "live",
    "half": "live", "final": "finished",
    "scheduled": "scheduled", "live": "live", "finished": "finished",
}


def parse_espn_matches(data: dict) -> list:
    """解析 ESPN 数据，时间保留 ISO 格式（备用源不做时区转换）"""
    events = data.get("events", [])
    if not events:
        return []

    now = datetime.now(BJ)

    parsed = []
    for event in events:
        comps = event.get("competitions", [{}])
        if not comps:
            continue
        comp = comps[0]
        competitors = comp.get("competitors", [])
        if len(competitors) < 2:
            continue

        home, away = competitors[0], competitors[1]
        h_score = to_score(home.get("score"))
        a_score = to_score(away.get("score"))

        raw_status = comp.get("status", {}).get("type", {}).get("name", "scheduled").lower()
        status = ESPN_STATUS_MAP.get(raw_status, "scheduled")

        date_str = comp.get("date") or event.get("date") or ""
        bj_time = date_str[11:16] if len(date_str) >= 16 else ""
        bj_date = date_str[:10] if len(date_str) >= 10 else ""

        stage = event.get("name", "")
        if "|" in stage:
            stage = stage.split("|")[-1].strip()

        # ESPN 没有球员数据
        parsed.append({
            "home_team": home.get("team", {}).get("displayName", "?"),
            "away_team": away.get("team", {}).get("displayName", "?"),
            "home_score": h_score,
            "away_score": a_score,
            "status": status,
            "bj_time": bj_time,
            "bj_date": bj_date,
            "stage": stage,
            "home_scorers": [],
            "away_scorers": [],
        })

    return parsed


# ============================================================
# 核心：获取今天（北京时间）的比赛
# ============================================================

def get_today_matches() -> list:
    """获取今天北京时间的比赛"""
    now = datetime.now(BJ)
    today_str = now.strftime("%Y-%m-%d")
    print(f"📅 北京时间现在: {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"🔍 只取北京日期 = {today_str} 的比赛")

    all_games = []

    # 数据源 1: worldcup26.ir
    print("\n--- 数据源 1: worldcup26.ir ---")
    raw = fetch_json("https://worldcup26.ir/get/games")
    if raw:
        games = parse_worldcup26_matches(raw)
        print(f"  ✅ 共 {len(games)} 场比赛")

        for g in games:
            print(f"     {g['bj_time']} {g['home_team']} vs {g['away_team']} [{g['status']}] BJ_date={g['bj_date']}")

        # 按北京时间过滤
        today_games = [g for g in games if g["bj_date"] == today_str]
        all_games.extend(today_games)
        print(f"  📌 今天北京时间的比赛: {len(today_games)} 场")
    else:
        print("  ⚠️ 获取失败")

    # 数据源 2: ESPN 备用
    if not all_games:
        print("\n--- 数据源 2: ESPN ---")
        raw = fetch_json("https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard")
        if raw:
            games = parse_espn_matches(raw)
            for g in games:
                if g["bj_date"] == today_str:
                    all_games.append(g)
            print(f"  📌 今天比赛: {len(all_games)} 场")

    # 去重
    seen = set()
    unique = []
    for g in all_games:
        key = (g["home_team"], g["away_team"])
        if key not in seen:
            seen.add(key)
            unique.append(g)

    print(f"\n📊 最终: {len(unique)} 场比赛")
    return unique


# ============================================================
# 格式化
# ============================================================

def format_scorers(scorers: list) -> str:
    """把 ["J. Quiñones 9'", "R. Jiménez 67'"] 变成单行文字"""
    if not scorers:
        return ""
    parts = []
    for s in scorers:
        # 清理多余的空白
        s = re.sub(r"\s+", " ", s).strip()
        parts.append(s)
    return " · ".join(parts)


def format_schedule(matches: list) -> str:
    """早上：当天赛程"""
    if not matches:
        return "📅 今天没有世界杯比赛，休息一天～"

    now = datetime.now(BJ)
    lines = [f"📅 世界杯 · {now.strftime('%m/%d')} 赛程预告", "─" * 20]

    finished = [m for m in matches if m["status"] == "finished"]
    live = [m for m in matches if m["status"] == "live"]
    upcoming = [m for m in matches if m["status"] == "scheduled"]

    if finished:
        lines.append(f"\n✅ 半夜已结束:")
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
            lines.append(line)
            # 进球球员
            hs_str = format_scorers(m.get("home_scorers", []))
            as_str = format_scorers(m.get("away_scorers", []))
            if hs_str:
                lines.append(f"    ⚽ {hs_str}")
            if as_str:
                lines.append(f"    ⚽ {as_str}")

    if live:
        lines.append(f"\n⚡ 进行中:")
        for m in live:
            hs = m["home_score"] if m["home_score"] is not None else "?"
            as_ = m["away_score"] if m["away_score"] is not None else "?"
            lines.append(f"  🟢 {m['home_team']} {hs} - {as_} {m['away_team']}")

    if upcoming:
        lines.append(f"\n⏳ 今天赛程:")
        for m in upcoming:
            s = f"  {m['bj_time']} {m['home_team']} vs {m['away_team']}"
            if m["stage"]:
                s += f" ({m['stage']})"
            lines.append(s)

    lines.append("\n─── via WorldCup Push ───")
    return "\n".join(lines)


def format_results(matches: list) -> str:
    """晚上：当天战报 + 进球球员"""
    if not matches:
        return "⚽ 今天没有世界杯比赛"

    now = datetime.now(BJ)
    lines = [f"⚽ 世界杯 · {now.strftime('%m/%d')} 战报", "─" * 20]

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
            # 进球球员
            hs_str = format_scorers(m.get("home_scorers", []))
            as_str = format_scorers(m.get("away_scorers", []))
            if hs_str:
                lines.append(f"    ↑ {hs_str}")
            if as_str:
                lines.append(f"    ↓ {as_str}")

    if live:
        lines.append(f"\n⚡ 还在踢 ({len(live)}):")
        for m in live:
            hs = m["home_score"] if m["home_score"] is not None else "?"
            as_ = m["away_score"] if m["away_score"] is not None else "?"
            lines.append(f"  🟢 {m['home_team']} {hs} - {as_} {m['away_team']}")

    if upcoming:
        lines.append(f"\n⏳ 还没踢 ({len(upcoming)}):")
        for m in upcoming:
            s = f"  {m['bj_time']} {m['home_team']} vs {m['away_team']}"
            if m["stage"]:
                s += f" ({m['stage']})"
            lines.append(s)

    lines.append("\n─── via WorldCup Push ───")
    return "\n".join(lines)


# ============================================================
# Bark 推送
# ============================================================

def send_bark(title: str, body: str, group: str = "世界杯") -> bool:
    if not BARK_KEY:
        print("\n❌ BARK_KEY 未设置")
        return False

    print(f"\n📱 推送中: {title}")
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
            if result.get("code") == 200:
                print(f"  ✅ 成功！")
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
    print("🌍 World Cup 2026 Push")
    print("=" * 40)

    raw_type = os.environ.get("PUSH_TYPE", "auto")
    now_hour = datetime.now(BJ).hour
    if raw_type == "auto":
        push_type = "morning" if now_hour < 15 else "evening"
    else:
        push_type = raw_type
    print(f"📋 类型: {'🌅 早间赛程' if push_type == 'morning' else '🌇 晚间战报'}")
    print()

    matches = get_today_matches()
    print()

    date_str = datetime.now(BJ).strftime("%m/%d")

    if not matches:
        msg = "今天没有世界杯比赛安排" if push_type == "morning" else "今天没有世界杯比赛"
        send_bark(f"⚽ 世界杯 · {date_str} 无比赛安排", msg)
        return

    body = format_schedule(matches) if push_type == "morning" else format_results(matches)
    title = f"📅 世界杯赛程 · {date_str}" if push_type == "morning" else f"⚽ 世界杯战报 · {date_str}"

    print(f"📋 内容:\n{body}")
    send_bark(title, body)
    print("\n✅ 完成！")


if __name__ == "__main__":
    main()
