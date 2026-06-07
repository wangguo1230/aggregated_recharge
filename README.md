# AskWhy 充值接入（独立工程）

对接第三方 [AskWhy 用户端 API](https://askwhy123.shop)，提供「校验卡密 → 校验 Session JSON → 充值 → 轮询进度 → 查订阅」的自助充值流程，并提供独立的「订阅查询」页。后端做反向代理并把卡密 / Session JSON **加密落库**，前端复用充值提交页样式。

第三方真实接口在 `https://askwhy123.shop/api/*`（非文档所写的 `/v1`），本工程已按抓包对齐：`cards/verify`、`token/verify`、`exchange/start`、`exchange/status`、`exchange/subscription`（POST，需 orderId+fetchToken）、`recharge/channels`。其中 `fetchToken` 即整段 Session JSON 字符串。

本工程与任何其他系统解耦，可单独部署。

## 目录结构

```
askwhy-recharge/
├── backend/            # FastAPI 服务（askwhy-center），端口默认 18424
│   ├── askwhy_recharge/
│   │   ├── settings.py   # 环境变量配置
│   │   ├── crypto.py     # Fernet 加密 + 指纹
│   │   ├── db.py         # SQLAlchemy 引擎（PostgreSQL）
│   │   ├── models.py     # askwhy_orders 表
│   │   ├── client.py     # AskWhy 出站客户端（curl_cffi）
│   │   ├── schemas.py    # 请求体模型
│   │   ├── app.py        # 路由 /api/askwhy/*
│   │   └── center_main.py
│   ├── pyproject.toml
│   └── .env.example
├── web/                # 客户端（Vite+Vue3+ElementPlus），dev 端口 5177
│   └── src/views/      # 充值三步向导 + 卡密查询（仅客户功能，无管理入口）
└── admin/              # 管理端（独立应用），dev 端口 5178，控制台风格
    └── src/views/AdminView.vue   # 口令登录 + 卡密映射 + 充值记录
```

> 客户端 `web/` 与管理端 `admin/` 是两个**完全独立**的前端应用：分别构建、分别部署、互不引用。客户站不含任何管理入口或代码。

## 后端

```bash
cd backend
cp .env.example .env          # 按需修改 ASKWHY_DATABASE_URL / ASKWHY_SECRET_KEY
uv run askwhy-center          # 或：pip install -e . && askwhy-center
```

- 监听 `http://0.0.0.0:18424`，首次启动自动建表 `askwhy_orders`。
- 路由：`/api/askwhy/{health,card/verify,card/status,exchange/create,exchange/status,exchange/subscription}`。
- 卡密、fetchToken 经 `ASKWHY_SECRET_KEY` 加密存储，另存指纹与后四位用于检索。

## 客户端（web）

```bash
cd web
npm install
npm run dev                   # http://127.0.0.1:5177，dev 代理 /api → 18424
npm run build                 # 产物在 web/dist
```

只含「充值」「卡密查询」两个面向客户的功能，**不含任何管理入口**。客户全程使用外部码，看不到真实 AskWhy 卡密与套餐前缀。

## 管理端（admin，独立应用）

```bash
cd admin
npm install
npm run dev                   # http://127.0.0.1:5178/wangguodong
npm run build                 # 产物在 admin/dist
```

- **独立应用，独立部署**（独立端口/域名），控制台风格页头，与客户站零引用。
- 入口路径默认 `/wangguodong`（可用 `VITE_ADMIN_PATH` 覆盖），其余路径回落到该入口。
- 口令：后端 `ASKWHY_ADMIN_TOKEN`（必填，生产改强随机值）；登录后以 Bearer 调用 admin 接口。
- 功能：① 卡密映射——录入真实卡密自动生成不含套餐信息的外部码、列表/启停/删除；② 充值记录——按订单号/外部码/邮箱查询订单、状态与订阅到期，真实卡密默认脱敏可一键显示。

> 安全建议：管理端只部署在内网或受信域名；后端 `ASKWHY_CORS_ALLOW_ORIGINS` 生产环境应收紧到客户站与管理端的实际域名。前端均可用 `VITE_ASKWHY_API_TARGET` 覆盖代理目标。

## 配置项

见 `backend/.env.example`，关键项：`ASKWHY_DATABASE_URL`（PostgreSQL，必填）、`ASKWHY_SECRET_KEY`（加密密钥，必填）、`ASKWHY_BASE_URL`、`ASKWHY_REQUEST_PROXY`、`ASKWHY_PORT`、`ASKWHY_CORS_ALLOW_ORIGINS`。
