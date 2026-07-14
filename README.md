# ✈️ 成都→北京大兴 低价机票监控

每天自动查询未来 7 天 成都→北京大兴 的航班，当发现含税总价 ≤ ¥750 时，通过 Bark 推送到你的 iPhone。

## 工作原理

```
GitHub Actions (每天 8:00)
    ↓ 调 Amadeus Flight API
查询 CTU→PKX + TFU→PKX 未来 7 天价格
    ↓ 发现 ≤ ¥750 的航班
Bark API → 你的 iPhone 📱
```

- 数据源：Amadeus 航空 API（全球 GDS，覆盖所有航司）
- 运行平台：GitHub Actions（免费，电脑不用开机）
- 推送渠道：Bark App（iPhone）

## 快速开始

### 1. 注册 Amadeus 免费账号

1. 打开 https://developers.amadeus.com/register
2. 注册（选 Individual/个人）
3. 登录后点 **Your Apps** → **Add a new application**
4. 应用名随意，如 `flight-monitor`
5. 拿到 **API Key** 和 **API Secret**

### 2. 配置 GitHub Secrets

在仓库 Settings → Secrets and variables → Actions → New repository secret：

| Name | Value |
|------|-------|
| `BARK_KEY` | `你的Bark Key` |
| `AMADEUS_API_KEY` | `Amadeus API Key` |
| `AMADEUS_API_SECRET` | `Amadeus API Secret` |

### 3. 启用 Actions

- 切到仓库 **Actions** 标签页
- 点 **✈️ 低价机票监控** → **Enable workflow**
- 点 **Run workflow** 手动测试一次

测试成功后，每天 8:00 自动运行。

## 文件说明

| 文件 | 说明 |
|------|------|
| `flight_monitor.py` | 主脚本（查航班 + 推送到 Bark） |
| `.github/workflows/flight-monitor.yml` | GitHub Actions 配置 |
| `requirements.txt` | Python 依赖 |

## 自定义

想改价格阈值、路线、提前天数？编辑 `flight_monitor.py` 顶部：

```python
PRICE_LIMIT = 750    # 价格上限
ROUTES = [("CTU","PKX"), ("TFU","PKX")]  # 航线
```

然后 `git commit && git push` 即可。
