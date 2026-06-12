"""Gift 提交页上游客户端（Claude Pro 充值走此通道，出站走 curl_cffi）。

上游响应结构：{"success": bool, "msg": str, "data": object|str, "code": str?}
统一在 base_url + api_prefix（默认 /api）下：
- GET  check?cdkey=xxx          查询 CDKEY（返回 data.app / gift_name / use_status 等）
- POST activate {cdkey, uid}    提交激活（Claude 只需 uid，无需 session_info）

返回上游原始 JSON（含 success 字段），由调用方判断业务结果；网络/解析异常抛 GiftApiError。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

from curl_cffi import requests

logger = logging.getLogger(__name__)


class GiftApiError(RuntimeError):
    """Gift 接口调用异常（网络/解析层面）。"""


@dataclass
class GiftClient:
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
            raise GiftApiError("缺少 GIFT_BASE_URL")

    # ---- 业务接口 ----
    def check(self, cdkey: str) -> dict[str, Any]:
        return self._request("GET", "check", params={"cdkey": cdkey})

    def activate(self, cdkey: str, uid: str) -> dict[str, Any]:
        # 激活非幂等：失败不重试，避免同一卡密重复提交导致重复充值。
        return self._request("POST", "activate", attempts=1, json={"cdkey": cdkey, "uid": uid})

    # ---- 内部 ----
    def _request(self, method: str, path: str, attempts: int | None = None, **kwargs: Any) -> dict[str, Any]:
        url = urljoin(f"{self.base_url}{self.api_prefix}/", path.lstrip("/"))
        headers = {"Accept": "application/json"}
        if method.upper() == "POST":
            headers["Content-Type"] = "application/json"
        proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
        total = max(1, int(attempts if attempts is not None else self.retry_attempts))
        last_error = ""
        for attempt in range(1, total + 1):
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
                logger.warning("Gift 请求异常 %s %s attempt=%s/%s err=%s", method, url, attempt, total, exc)
                if attempt < total:
                    time.sleep(self.retry_interval_seconds)
                continue

            elapsed = round(time.monotonic() - started, 3)
            try:
                payload = response.json()
            except Exception:  # noqa: BLE001 - 非 JSON 响应
                last_error = f"HTTP {response.status_code} 非 JSON 响应"
                logger.warning("Gift 响应非 JSON %s %s status=%s", method, url, response.status_code)
                if attempt < total:
                    time.sleep(self.retry_interval_seconds)
                continue

            logger.info(
                "Gift 请求完成 %s %s status=%s success=%s %ss",
                method, url, response.status_code, payload.get("success"), elapsed,
            )
            if not isinstance(payload, dict):
                raise GiftApiError("Gift 响应格式异常")
            return payload

        raise GiftApiError(last_error or "Gift 请求失败")
