# ⚽ 世界杯推送 - World Cup 2026 Push

每天推送世界杯比分到你的 iPhone（通过 Bark App）。

## ✨ 功能

| 时间 | 推送内容 |
|------|---------|
| 🌅 **08:00** | 当天比赛赛程（队伍 + 时间） |
| 🌇 **21:00** | 当天比赛结果（比分 + 胜者） |

- 数据来源：[worldcup26.ir](https://worldcup26.ir)（免费开源，无需 API Key）
- 备用来源：ESPN 公共 API
- 托管运行：GitHub Actions（免费，电脑不用开机）

## 🚀 快速开始

### 前置条件

1. iPhone 安装 [Bark App](https://apps.apple.com/app/id1555405475)
2. 注册 Bark 获取你的设备 Key

### 步骤

#### 1. 把代码传到 GitHub

```bash
# 在你电脑上
cd D:\区块链作业\worldcup-push

git init
git add .
git commit -m "🎉 添加世界杯推送脚本"

# 在 GitHub 上新建一个仓库（不要勾选添加 README）
# 然后回到这里：
git remote add origin https://github.com/你的用户名/你的仓库名.git
git branch -M main
git push -u origin main
```

#### 2. 在 GitHub 上配置 Bark Key

1. 打开你的 GitHub 仓库页面
2. 点 **Settings** → **Secrets and variables** → **Actions**
3. 点 **New repository secret**
4. Name: `BARK_KEY`
5. Secret: `9rYX3vSr5ZG7B2GaDeMTaK`（你的 Bark Key）
6. 点 **Add secret**

#### 3. 启用 Actions

1. 切到仓库的 **Actions** 标签页
2. 如果弹出提示说"Workflows 被禁用"，点 **I understand my workflows, go ahead and enable them**
3. 点左边的 **⚽ 世界杯推送**
4. 点 **Enable workflow**
5. 点右边的 **Run workflow** → 选 `morning` → 点 **Run** 测试一次

> ✅ 测试成功后，每天早上 08:00 和晚上 21:00 会自动推送

## 🔧 手动测试

在 GitHub Actions 页面：
- **Run workflow** → `morning` → 测试早上推送
- **Run workflow** → `evening` → 测试晚上推送

## 📂 文件说明

| 文件 | 说明 |
|------|------|
| `worldcup_push.py` | 主要脚本（抓数据 + 推送到 Bark） |
| `.github/workflows/worldcup.yml` | GitHub Actions 定时任务配置 |
| `requirements.txt` | 依赖（纯标准库，无需安装额外包） |

## 🔔 还能推送什么？

这套框架完全可以复用，想加新功能：
1. 在 `worldcup_push.py` 里加一个新的数据源函数
2. 在主流程里调用它
3. 内容会合并到每天早上/晚上的推送里

比如加天气、热搜、股票……欢迎自行扩展！
