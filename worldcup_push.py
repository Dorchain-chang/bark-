#!/usr/bin/env python3
"""
World Cup 2026 推送脚本
每天早上 8:00 推送当天赛程，晚上 21:00 推送比赛结果
通过 Bark App 推送到 iPhone
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# ============================================================
# 配置（会在 GitHub Actions 中通过环境变量设置）
# ============================================================
BARK_KEY = os.environ.get("BARK_KEY", "")
BARK_URL = f"https://api.day.app/{BARK_KEY}/"

# 时区 (UTC+8 北京时间)
TZ_OFFSET = timedelta(hours=8)

# ============================================================
# 数据源
# ============================================================

# 数据源 1：worldcup26.ir（免费开源，无需 Key）
WORLDCUP26_API = "https://worldcup26.ir/get/games"

# 数据源 2：ESPN 公共 API（备用，无需 Key）
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


def fetch_matches_from_worldcup26() -> Optional[list]:
    """从 worldcup26.ir 获取所有比赛"""
    print(f"  📡 尝试数据源: worldcup26.ir ...")
    data = fetch_json(WORLDCUP26_API)
    if not data:
        return None
    print(f"  ✅ 数据获取成功，原始数据类型: {type(data).__name__}")
    print(f"  📄 原始数据(截断): {json.dumps(data, ensure_ascii=False)[:1000]}")
    return data


def fetch_matches_from_espn() -> Optional[list]:
    """从 ESPN 获取比赛数据（备用）"""
    print(f"  📡 尝试数据源: ESPN ...")
    data = fetch_json(ESPN_API)
    if not data:
        return None
    print(f"  ✅ ESPN 数据获取成功")
    return data


# ============================================================
# 数据解析
# ============================================================

def parse_worldcup26_matches(data) -> Optional[list]:
    """解析 worldcup26.ir 的比赛数据"""
    try:
        # 数据可能是 { "data": [...] } 或 { "matches": [...] } 或 直接是列表
        if isinstance(data, list):
            matches = data
        elif isinstance(data, dict):
            matches = (data.get("data") or data.get("matches") or data.get("games") or
                       data.get("results") or [])
        else:
            return None

        if not matches:
            return None

        parsed = []
        for m in matches:
            if not isinstance(m, dict):
                continue
            # 尝试多种字段名
            home_team = (m.get("home_team") or m.get("homeTeam") or m.get("home_team_en") or
                         m.get("home", {}).get("name") or "?")
            away_team = (m.get("away_team") or m.get("awayTeam") or m.get("away_team_en") or
                         m.get("away", {}).get("name") or "?")
            home_score = (m.get("home_score") if m.get("home_score") is not None else
                         m.get("homeScore") if m.get("homeScore") is not None else
                         m.get("home", {}).get("score"))
            away_score = (m.get("away_score") if m.get("away_score") is not None else
                         m.get("awayScore") if m.get("awayScore") is not None else
                         m.get("away", {}).get("score"))
            status = (m.get("status") or m.get("status_name") or
                     m.get("statusName") or "scheduled")
            # 时间
            match_time = (m.get("date") or m.get("datetime") or m.get("time") or
                         m.get("match_time") or m.get("matchTime") or "")
            # 阶段
            stage = (m.get("stage") or m.get("round_name") or m.get("roundName") or "")

            # 用队伍名生成唯一键去重
            parsed.append({
                "home_team": str(home_team),
                "away_team": str(away_team),
                "home_score": int(home_score) if home_score is not None else None,
                "away_score": int(away_score) if away_score is not None else None,
                "status": str(status).lower(),
                "time": str(match_time),
                "stage": str(stage),
            })
        return parsed if parsed else None
    except Exception as e:
        print(f"  ⚠️ 解析 worldcup26.ir 数据出错: {e}")
        return None


def parse_espn_matches(data) -> Optional[list]:
    """解析 ESPN 的比赛数据"""
    try:
        events = data.get("events", [])
        if not events:
            return None

        parsed = []
        now = datetime.now(timezone.utc)

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

            home_score = home.get("score")
            away_score = away.get("score")
            status = comp.get("status", {}).get("type", {}).get("name", "scheduled")
            date_str = comp.get("date") or event.get("date") or ""

            parsed.append({
                "home_team": home.get("team", {}).get("displayName", "?"),
                "away_team": away.get("team", {}).get("displayName", "?"),
                "home_score": int(home_score) if home_score is not None else None,
                "away_score": int(away_score) if away_score is not None else None,
                "status": str(status).lower(),
                "time": date_str,
                "stage": event.get("name", ""),
            })
        return parsed if parsed else None
    except Exception as e:
        print(f"  ⚠️ 解析 ESPN 数据出错: {e}")
        return None


# ============================================================
# 核心：获取并过滤今天的比赛
# ============================================================

def get_today_matches() -> list:
    """获取今天的比赛（先 primary，失败则 fallback）"""
    now = datetime.now(timezone.utc) + TZ_OFFSET
    today_str = now.strftime("%Y-%m-%d")
    print(f"📅 北京时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔍 查找日期: {today_str} 的比赛")

    raw = None
    matches = None

    # 1. 尝试 worldcup26.ir
    print("\n--- 数据源 1: worldcup26.ir ---")
    raw = fetch_matches_from_worldcup26()
    if raw:
        matches = parse_worldcup26_matches(raw)

    # 2. 失败则尝试 ESPN
    if not matches:
        print("\n--- 数据源 2: ESPN (备用) ---")
        raw = fetch_matches_from_espn()
        if raw:
            matches = parse_espn_matches(raw)

    if not matches:
        print("\n❌ 所有数据源均失败")
        return []

    print(f"\n📊 共获取到 {len(matches)} 场比赛（全部）")

    # 按今天日期过滤（如果 API 返回的数据有时间字段）
    today_matches = []
    for m in matches:
        time_str = m["time"]
        if time_str:
            # 尝试从时间字符串中提取 YYYY-MM-DD
            try:
                match_date = time_str[:10]
                if match_date == today_str:
                    today_matches.append(m)
                    continue
            except (IndexError, ValueError):
                pass
        # 如果没时间或者不匹配，把所有数据都留着
        # （有些 API 只返回正在进行的比赛）
        today_matches.append(m)

    # 去重（按队伍组合）
    seen = set()
    unique = []
    for m in today_matches:
        key = (m["home_team"], m["away_team"])
        if key not in seen:
            seen.add(key)
            unique.append(m)

    print(f"📅 今天的比赛: {len(unique)} 场")
    return unique


# ============================================================
# 格式化消息
# ============================================================

def format_schedule(matches: list) -> str:
    """格式化：当天赛程（早上推送）"""
    if not matches:
        today = (datetime.now(timezone.utc) + TZ_OFFSET).strftime("%m/%d")
        return f"📅 {today} 世界杯 | 今天没有比赛，休息一天～"

    lines = []
    today = (datetime.now(timezone.utc) + TZ_OFFSET).strftime("%m/%d")
    lines.append(f"📅 世界杯 · {today} 赛程预告")
    lines.append("─" * 20)

    # 区分进行中/未开始的比赛
    upcoming = [m for m in matches if m["status"] in ("scheduled", "pre", "pre_game", "")]
    in_progress = [m for m in matches if m["status"] in ("in_progress", "live", "in progress")]
    finished = [m for m in matches if m["status"] in ("finished", "complete", "completed", "final")]

    if upcoming:
        lines.append(f"\n⏳ 未开始 ({len(upcoming)}):")
        for m in upcoming:
            time_display = m.get("time", "")[11:16] if len(m.get("time", "")) > 11 else (m.get("time", "") or "待定")
            stage = f" [{m['stage']}]" if m['stage'] and m['stage'] != "?" else ""
            lines.append(f"  {time_display} {m['home_team']} vs {m['away_team']}{stage}")

    if in_progress:
        lines.append(f"\n⚡ 进行中 ({len(in_progress)}):")
        for m in in_progress:
            hs = m["home_score"] if m["home_score"] is not None else "?"
            as_ = m["away_score"] if m["away_score"] is not None else "?"
            lines.append(f"  🟢 {m['home_team']} {hs} - {as_} {m['away_team']}")

    if finished and not matches:  # 早上一般不显示已结束的
        pass

    lines.append("\n─── via WorldCup Push ───")
    return "\n".join(lines)


def format_results(matches: list) -> str:
    """格式化：当天比赛结果（晚上推送）"""
    if not matches:
        today = (datetime.now(timezone.utc) + TZ_OFFSET).strftime("%m/%d")
        return f"⚽ {today} 世界杯 | 今天没有比赛"

    lines = []
    today = (datetime.now(timezone.utc) + TZ_OFFSET).strftime("%m/%d")
    lines.append(f"⚽ 世界杯 · {today} 战报")
    lines.append("─" * 20)

    finished = [m for m in matches if m["status"] in ("finished", "complete", "completed", "final")]
    in_progress = [m for m in matches if m["status"] in ("in_progress", "live", "in progress")]
    upcoming = [m for m in matches if m["status"] in ("scheduled", "pre", "pre_game", "")]
    unknown = [m for m in matches if m["status"] not in ("finished", "complete", "completed", "final",
                                                           "in_progress", "live", "in progress",
                                                           "scheduled", "pre", "pre_game", "")]

    if finished:
        lines.append(f"\n✅ 已结束 ({len(finished)}):")
        for m in finished:
            hs = m["home_score"] if m["home_score"] is not None else "?"
            as_ = m["away_score"] if m["away_score"] is not None else "?"
            stage = f" [{m['stage']}]" if m['stage'] and m['stage'] != "?" else ""
            lines.append(f"  {m['home_team']} {hs} - {as_} {m['away_team']}{stage}")
            # 赢方标记
            if m["home_score"] is not None and m["away_score"] is not None:
                if m["home_score"] > m["away_score"]:
                    lines[-1] += " 👑"
                elif m["away_score"] > m["home_score"]:
                    lines[-1] += " 👑"
                else:
                    lines[-1] += " 🤝"

    if in_progress:
        lines.append(f"\n⚡ 还在踢 ({len(in_progress)}):")
        for m in in_progress:
            hs = m["home_score"] if m["home_score"] is not None else "?"
            as_ = m["away_score"] if m["away_score"] is not None else "?"
            lines.append(f"  🟢 {m['home_team']} {hs} - {as_} {m['away_team']}")

    if upcoming:
        lines.append(f"\n⏳ 还没踢 ({len(upcoming)}):")
        for m in upcoming:
            time_display = m.get("time", "")[11:16] if len(m.get("time", "")) > 11 else (m.get("time", "") or "待定")
            lines.append(f"  {time_display} {m['home_team']} vs {m['away_team']}")

    lines.append("\n─── via WorldCup Push ───")
    return "\n".join(lines)


# ============================================================
# Bark 推送
# ============================================================

def send_bark(title: str, body: str, group: str = "世界杯") -> bool:
    """通过 Bark API 推送通知到 iPhone"""
    if not BARK_KEY:
        print("❌ 未设置 BARK_KEY 环境变量")
        print("💡 请在 GitHub 仓库 Settings → Secrets → Actions 中添加 BARK_KEY")
        return False

    print(f"\n📱 推送通知...")
    print(f"   标题: {title}")
    print(f"   内容预览: {body[:100]}...")

    # Bark 支持 POST JSON（功能更丰富）
    payload = json.dumps({
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
        headers={
            "Content-Type": "application/json; charset=utf-8",
        },
    )

    try:
        with urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("code") == 200:
                print(f"  ✅ 推送成功！")
                return True
            else:
                print(f"  ❌ 推送失败: {result}")
                return False
    except (URLError, HTTPError, OSError, json.JSONDecodeError) as e:
        print(f"  ❌ 推送网络错误: {e}")
        return False


# ============================================================
# 主入口
# ============================================================

def main():
    print("=" * 40)
    print("🌍 World Cup 2026 Push")
    print("=" * 40)
    print()

    # 确定推送类型
    # GitHub Actions 会设置 PUSH_TYPE = morning 或 evening
    push_type = os.environ.get("PUSH_TYPE", "morning")

    # 获取今天的比赛
    matches = get_today_matches()
    print()

    if not matches:
        print("⚠️ 没有获取到比赛数据，仍发送通知告知用户")
        if push_type == "morning":
            body = (datetime.now(timezone.utc) + TZ_OFFSET).strftime("今天是 %m/%d\n今天没有世界杯比赛安排\n\n有问题可以查看一下 API 数据源状态")
            send_bark("📅 世界杯 · 今日无赛程", body)
        else:
            body = (datetime.now(timezone.utc) + TZ_OFFSET).strftime("今天是 %m/%d\n今天没有世界杯比赛\n\n今晚好好休息！")
            send_bark("⚽ 世界杯 · 今日无比赛", body)
        return

    # 生成推送内容
    if push_type == "morning":
        title = f"📅 世界杯赛程 · {(datetime.now(timezone.utc) + TZ_OFFSET).strftime('%m/%d')}"
        body = format_schedule(matches)
    else:
        title = f"⚽ 世界杯战报 · {(datetime.now(timezone.utc) + TZ_OFFSET).strftime('%m/%d')}"
        body = format_results(matches)

    # 发送推送
    print(f"📋 推送类型: {push_type}")
    print(f"📋 推送标题: {title}")
    print(f"📋 推送内容:\n{body}")

    send_bark(title, body)
    print("\n✅ 完成！")


if __name__ == "__main__":
    main()
