# ✈️ Flight Price Monitor · 低价机票推送系统

> **AI-assisted engineering demo** — 一个从需求到上线的完整工程闭环

## 📋 概述

全自动机票价格监控工具。每天定时查询**成都→北京大兴**未来指定日期的航班价格，当低于设定阈值时，通过 **Bark App** 推送通知到 iPhone。

| 特性 | 说明 |
|------|------|
| 🎯 **目标航线** | 成都(CTU/TFU) → 北京大兴(PKX) |
| ⏰ **监控频率** | 每天 6:00-20:00 每 2 小时执行一次 |
| 💰 **价格阈值** | ≤ ¥850（含税总价） |
| 📱 **推送方式** | Bark (Apple Push Notification) |
| 💵 **运行成本** | 完全免费 |
| 🚫 **无需注册** | 不依赖任何第三方付费 API |

---

## 🏗 系统架构

```
┌─ User ─────────────────────────────┐
│  需求：「盯 7/23-24 成都到北京机票」│
└──────────────┬─────────────────────┘
               │ (自然语言描述需求)
               ▼
┌─ Claude AI ─────────────────────────┐
│  代码生成 · Debug · 方案迭代         │
└──────────────┬─────────────────────┘
               │ (推送到 GitHub)
               ▼
┌─ GitHub Actions ────────────────────┐
│  定时触发器 (cron) ← 每天 8 次       │
│  ┌─────────────────────────────┐    │
│  │ Python Script                │    │
│  │  ├─ Playwright → Google      │    │
│  │  │   Flights (数据获取)      │    │
│  │  ├─ Price Parser (¥解析)     │    │
│  │  └─ Bark API (推送通知)      │    │
│  └─────────────────────────────┘    │
└──────────────┬─────────────────────┘
               ▼
┌─ iPhone ────────────────────────────┐
│  🔔 推送：「成都→北京 最低¥XXX」    │
└─────────────────────────────────────┘
```

---

## 🛠 技术栈

| 类别 | 技术 | 用途 |
|------|------|------|
| **语言** | Python 3.11 | 核心逻辑 |
| **Web 自动化** | Playwright + Chromium | 数据抓取与反反爬 |
| **反检测** | Playwright-Stealth | 绕过 bot 检测 |
| **CI/CD** | GitHub Actions | 定时执行 + 环境管理 |
| **推送** | Bark API (Apple APNs) | iPhone 即时通知 |
| **版本控制** | Git / GitHub | 完整迭代历史可见 |

---

## 🎯 项目亮点

### 1. 零成本生产级部署
- 完全依赖 GitHub Actions 免费额度（2000 min/月）
- 无需云服务器、无需数据库、无需注册任何第三方服务
- 总运行成本：**¥0**

### 2. 多方案迭代能力
项目经历了 **3 次技术方案重构**：

```
v1: Amadeus API → 发现需要注册外部服务
v2: Google Flights 爬虫 → 发现反爬机制
v3: Playwright + Stealth → 成功获取数据 ✅
```

这模拟了真实工程中的**问题发现→方案评估→技术选型→落地**全过程。

### 3. 完整的 DevOps 实践
- CI/CD 流水线自动化
- 敏感信息管理（GitHub Secrets）
- 定时任务配置（Cron 表达式）
- 远程 Debug（GitHub Actions 日志）

### 4. AI 辅助开发工作流
整个项目由 Claude AI 辅助完成，体现了 **prompt engineering → 代码生成 → 调试迭代 → 部署交付** 的高效开发模式。

---

## 📁 项目结构

```
├── flight_monitor.py         # 主程序（抓取 + 解析 + 推送）
├── .github/workflows/
│   └── flight-monitor.yml    # GitHub Actions 流水线配置
├── requirements.txt          # Python 依赖
├── .gitignore
└── README.md
```

---

## 🚀 快速开始

### 前置条件

1. iPhone 安装 [Bark App](https://apps.apple.com/app/id1555405475)
2. 获取 Bark 设备 Key

### 部署

```bash
# 1. 克隆仓库
git clone <your-repo-url>
cd flight-monitor

# 2. 配置 GitHub Secrets
# 在 GitHub 仓库 Settings → Secrets → Actions 添加：
# - BARK_KEY: 你的 Bark 设备 Key

# 3. 启用 GitHub Actions
# 仓库 Actions 标签页 → Enable workflow
```

### 配置说明

编辑 `flight_monitor.py` 顶部的常量即可自定义：

```python
TARGET_DATES = ["2026-07-23", "2026-07-24"]  # 目标出发日期
PRICE_LIMIT = 850                              # 价格阈值（含税）
MONITOR_UNTIL = "2026-07-20"                   # 监控截止日期
```

---

## 📊 开发过程数据

- **迭代次数**: 15+ 次 commit
- **技术方案重构**: 3 次
- **Bug 修复**: 5+ 次（缩进错误、超时、选择器适配、反爬对抗）
- **从需求到上线**: < 2 天

---

## 📝 License

MIT
