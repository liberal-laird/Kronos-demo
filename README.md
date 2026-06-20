# Kronos-demo — Stock Probabilistic Forecasting Platform

基于 [NeoQuasar/Kronos](https://huggingface.co/NeoQuasar/Kronos-base) 时序预测模型的美股日线预测平台。前后端分离架构，后端使用 Python Sanic + Tortoise ORM + PostgreSQL，前端使用 Vue 3 + ECharts。

## 功能特性

- **Kronos 时序预测**: 调用 Kronos Transformer 模型生成多轨迹概率价格预测（含价格和成交量）
- **预测指标**: 自动计算上行概率（Upside Probability）和波动率放大概率（Vol Amplification Probability）
- **可视化图表**: ECharts 双图面板（收盘价曲线 + 成交量柱状图），含历史数据和预测区间
- **定时自动预测**: 每个交易日 UTC 21:05（美股收盘后）自动预测预设股票列表
- **历史管理**: 浏览、查看、删除历史预测记录

## 项目结构

```
Kronos-demo/
├── backend/                   # 后端 Sanic 应用
│   ├── server.py              # Sanic 入口, CORS, ORM 生命周期
│   ├── config.py              # 数据库/模型/定时任务配置
│   ├── models/
│   │   └── prediction.py      # Tortoise ORM: Prediction, PredictionPoint
│   ├── routes/
│   │   ├── stocks.py          # GET /api/stocks
│   │   └── predictions.py     # POST/GET/DELETE /api/predictions
│   ├── services/
│   │   ├── data_fetcher.py    # yfinance 美股数据获取
│   │   └── predictor.py       # Kronos 模型加载 + 推理 + 指标计算
│   └── tasks/
│       └── scheduler.py       # APScheduler 定时任务
├── frontend/                  # 前端 Vue 3 应用
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js         # Vite + API 代理配置
│   └── src/
│       ├── main.js            # Vue 入口 + Router
│       ├── App.vue            # 根布局
│       ├── router/index.js    # 路由定义
│       ├── api/index.js       # Axios API 封装
│       ├── views/
│       │   ├── Dashboard.vue      # 主面板（选股 + 预测 + 图表）
│       │   ├── PredictionDetail.vue  # 预测详情 + 数据表
│       │   └── PredictionHistory.vue # 预测历史列表
│       └── components/
│           ├── StockSelector.vue   # 股票选择下拉框
│           ├── PredictionChart.vue # ECharts 价格+成交量双图
│           └── MetricsCard.vue     # 上行概率/波动率指标卡片
├── model/                     # Kronos 模型代码（PyTorch）
│   ├── __init__.py
│   ├── kronos.py              # Kronos, KronosTokenizer, KronosPredictor
│   └── module.py              # Transformer / BSQuantizer 等组件
├── pyproject.toml             # Python 依赖
└── update_predictions_us_stock.py  # 原单脚本（已废弃）
```

## 快速开始

### 环境要求

- Python >= 3.9
- PostgreSQL（建议 15+，使用 [Postgres.app](https://postgresapp.com/) 安装）
- Node.js >= 18（前端构建）

### 1. 安装后端依赖

```bash
# 使用 uv
uv sync

# 或使用 pip
pip install -r requirements.txt
```

### 2. 配置数据库

创建 PostgreSQL 数据库，并设置环境变量：

```bash
# 创建数据库
psql -U postgres -c "CREATE DATABASE kronos_demo;"

# 设置环境变量（或使用默认值 localhost:5432/postgres/postgres/kronos_demo）
export DB_HOST=localhost
export DB_PORT=5432
export DB_USER=postgres
export DB_PASSWORD=postgres
export DB_NAME=kronos_demo
```

可编辑 `backend/config.py` 更改预设股票列表、预测参数等。

### 3. 启动后端

```bash
cd Kronos-demo
python -m backend.server
```

首次启动会自动：
- 从 HuggingFace 下载 Kronos 模型（约 400MB，缓存至 `hf_model/`）
- 创建数据库表 `predictions` 和 `prediction_points`
- 启动定时任务调度器
- 在 `http://localhost:8000` 启动服务

### 4. 启动前端

```bash
cd Kronos-demo/frontend
npm install
npm run dev
```

访问 `http://localhost:5173` 即可使用。

### 5. 手动触发预测

```bash
# 对 AAPL 触发一次预测
curl -X POST http://localhost:8000/api/predictions \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL"}'
```

## API 文档

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| GET | `/api/stocks` | 获取预设股票列表 |
| POST | `/api/predictions` | 触发预测 `{symbol, interval?, hist_points?, pred_horizon?, n_predictions?}` → `202` |
| GET | `/api/predictions` | 预测列表 `?symbol=AAPL&limit=20&offset=0` |
| GET | `/api/predictions/latest` | 最新预测 `?symbol=AAPL` |
| GET | `/api/predictions/:id` | 预测详情（含数据点） |
| DELETE | `/api/predictions/:id` | 删除预测 |

POST `/api/predictions` 为异步模式：立即返回 `202` 和 `prediction_id`（status=pending），预测在后台执行，完成后自动更新为 completed。预测通常耗时 30-60 秒。

## 配置说明

主要配置项在 `backend/config.py`：

```python
# 预测参数
DEFAULT_SYMBOL = "AAPL"
DEFAULT_PRED_HORIZON = 10      # 预测未来交易日数
DEFAULT_N_PREDICTIONS = 30     # 采样轨迹数
DEFAULT_HIST_POINTS = 252      # 历史 K 线数

# 预设股票列表
PRESET_STOCKS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", ...]

# 定时任务
SCHEDULE_HOUR_UTC = 21
SCHEDULE_MINUTE_UTC = 5
SCHEDULE_SYMBOLS = ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"]
```

## 技术栈

| 层 | 技术 |
|---|---|
| 后端框架 | Sanic 25.x |
| ORM | Tortoise ORM + asyncpg |
| 数据库 | PostgreSQL |
| AI 模型 | Kronos (NeoQuasar) — PyTorch Transformer |
| 数据源 | yfinance (Yahoo Finance) |
| 前端框架 | Vue 3 (Composition API) |
| 构建工具 | Vite |
| 图表 | ECharts 5 + vue-echarts |
| HTTP 客户端 | Axios |
| 定时任务 | APScheduler |
