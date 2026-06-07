"""AskWhy 用户端 API 客户端（出站走 curl_cffi，与仓库其他出站调用一致）。

路径以实际抓包为准，统一在 base_url + api_prefix（默认 /api）下：
- POST cards/verify           校验卡密
- POST token/verify           校验 Session JSON（请求体字段名为 fetchToken，值为整段 session JSON）
- POST exchange/start         创建充值订单
- GET  exchange/status        查询订单状态
- POST exchange/subscription  查询订阅（需带 orderId + fetchToken）
- GET  recharge/channels      可用充值渠道
- POST cards/batch-query      批量查询卡密状态

返回 AskWhy 原始 JSON（含 ok 字段），由调用方判断业务结果；网络/解析异常抛 AskWhyApiError。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

from curl_cffi import requests

logger = logging.getLogger(__name__)


class AskWhyApiError(RuntimeError):
    """AskWhy 接口调用异常（网络/解析层面）。"""


@dataclass
class AskWhyClient:
    base_url: str
    api_prefix: str = "/api"
    proxy: str = ""
    timeout: int = 60
    retry_attempts: int = 2
    retry_interval_seconds: float = 1.5

    def __post_init__(self) -> None:
        self.base_url = str(self.base_url or "").strip().rstrip("/")
        self.api_prefix = "/" + str(self.api_prefix or "/api").strip().strip("/")
        if not self.base_url:
            raise AskWhyApiError("缺少 ASKWHY_BASE_URL")

    # ---- 业务接口 ----
    def verify_card(self, card_code: str) -> dict[str, Any]:
        return self._request("POST", "cards/verify", json={"cardCode": card_code})

    def verify_token(self, fetch_token: str) -> dict[str, Any]:
        return self._request("POST", "token/verify", json={"fetchToken": fetch_token})

    def cards_batch_query(self, card_codes: list[str]) -> dict[str, Any]:
        return self._request("POST", "cards/batch-query", json={"cardCodes": card_codes})

    def channels(self) -> dict[str, Any]:
        return self._request("GET", "recharge/channels")

    def create_exchange(self, card_code: str, fetch_token: str) -> dict[str, Any]:
        return self._request(
            "POST", "exchange/start", json={"cardCode": card_code, "fetchToken": fetch_token}
        )

    def exchange_status(self, order_id: str) -> dict[str, Any]:
        return self._request("GET", "exchange/status", params={"orderId": order_id})

    def exchange_subscription(self, order_id: str, fetch_token: str) -> dict[str, Any]:
        return self._request(
            "POST", "exchange/subscription", json={"orderId": order_id, "fetchToken": fetch_token}
        )

    # ---- 内部 ----
    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = urljoin(f"{self.base_url}{self.api_prefix}/", path.lstrip("/"))
        headers = {"Accept": "application/json"}
        if method.upper() == "POST":
            headers["Content-Type"] = "application/json"
        proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
        attempts = max(1, int(self.retry_attempts))
        last_error = ""
        for attempt in range(1, attempts + 1):
            started = time.monotonic()
            try:
                response = requests.request(
                    method.upper(),
                    url,
                    headers=headers,
                    proxies=proxies,
                    timeout=max(1, int(self.timeout)),
                    **kwargs,
                )
            except Exception as exc:  # noqa: BLE001 - curl_cffi 抛出多种网络异常
                last_error = str(exc)
                logger.warning("AskWhy 请求异常 %s %s attempt=%s/%s err=%s", method, url, attempt, attempts, exc)
                if attempt < attempts:
                    time.sleep(self.retry_interval_seconds)
                continue

            elapsed = round(time.monotonic() - started, 3)
            try:
                payload = response.json()
            except Exception:  # noqa: BLE001 - 非 JSON 响应
                last_error = f"HTTP {response.status_code} 非 JSON 响应"
                logger.warning("AskWhy 响应非 JSON %s %s status=%s", method, url, response.status_code)
                if attempt < attempts:
                    time.sleep(self.retry_interval_seconds)
                continue

            logger.info("AskWhy 请求完成 %s %s status=%s ok=%s %ss", method, url, response.status_code, payload.get("ok"), elapsed)
            if not isinstance(payload, dict):
                raise AskWhyApiError("AskWhy 响应格式异常")
            return payload

        raise AskWhyApiError(last_error or "AskWhy 请求失败")
