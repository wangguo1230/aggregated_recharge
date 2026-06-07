"""AskWhy 充值接入服务（独立工程）。

对接第三方 AskWhy 用户端 API（https://askwhy123.shop/v1/*）：
1. 作为前端到 AskWhy 的反向代理，规避浏览器跨域并隐藏第三方地址；
2. 把用户提交的卡密与 fetchToken 加密落库（PostgreSQL），便于对账与售后；
3. 转发订单状态与订阅查询。

本工程自带配置、数据库、加密、HTTP 客户端与 FastAPI 应用，不依赖任何外部业务包。
"""

from __future__ import annotations

from pathlib import Path

# PROJECT_ROOT 指向 backend/ 目录，.env 默认从这里加载。
PROJECT_ROOT = Path(__file__).resolve().parent.parent

__all__ = ["PROJECT_ROOT"]
