"""软件订阅渠道（ChatGPT 兑换 API）上游客户端（出站走 curl_cffi）。

统一在 base_url + api_prefix（默认 /api）下：
- POST external/redeem/verify   {cdk, platformCredential}            验证兑换
- POST external/redeem/confirm  {cdk, confirm:true, platformCredential} 确认兑换（实际充值）

platformCredential = {"platform":"chatgpt","data": <账号数据>}；data 为 ChatGPT 会话 JSON
（含 user/account/accessToken）。返回 {"success":bool, "data"|"error":...}。
网络/解析异常抛 SoftApiError；base_url 未配置时也抛 SoftApiError（允许应用先启动）。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

from curl_cffi import requests

logger = logging.getLogger(__name__)


class SoftApiError(RuntimeError):
    """软件订阅渠道接口调用异常（网络/解析/未配置层面）。"""


@dataclass
class SoftClient:
    base_url: str
    api_prefix: str = "/api"
    proxy: str = ""
    timeout: int = 60
    retry_attempts: int = 2
    retry_interval_seconds: float = 1.5

    def __post_init__(self) -> None:
        # 允许空 base_url 构造（host 待配置），仅在真正请求时报错，避免拖垮应用启动。
        self.base_url = str(self.base_url or "").strip().rstrip("/")
        self.api_prefix = "/" + str(self.api_prefix or "/api").strip().strip("/")

    # ---- 业务接口 ----
    def _credential(self, credential_data: dict[str, Any]) -> dict[str, Any]:
        return {"platform": "chatgpt", "data": credential_data}

    def verify(self, cdk: str, credential_data: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST", "external/redeem/verify", json={"cdk": cdk, "platformCredential": self._credential(credential_data)}
        )

    def confirm(self, cdk: str, credential_data: dict[str, Any]) -> dict[str, Any]:
        # 确认即实际兑换，非幂等：失败不重试。
        return self._request(
            "POST",
            "external/redeem/confirm",
            attempts=1,
            json={"cdk": cdk, "confirm": True, "platformCredential": self._credential(credential_data)},
        )

    # ---- 内部 ----
    def _request(self, method: str, path: str, attempts: int | None = None, **kwargs: Any) -> dict[str, Any]:
        if not self.base_url:
            raise SoftApiError("缺少 SOFT_BASE_URL（软件订阅渠道上游地址未配置）")
        url = urljoin(f"{self.base_url}{self.api_prefix}/", path.lstrip("/"))
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
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
                logger.warning("Soft 请求异常 %s %s attempt=%s/%s err=%s", method, url, attempt, total, exc)
                if attempt < total:
                    time.sleep(self.retry_interval_seconds)
                continue

            elapsed = round(time.monotonic() - started, 3)
            try:
                payload = response.json()
            except Exception:  # noqa: BLE001 - 非 JSON 响应
                last_error = f"HTTP {response.status_code} 非 JSON 响应"
                logger.warning("Soft 响应非 JSON %s %s status=%s", method, url, response.status_code)
                if attempt < total:
                    time.sleep(self.retry_interval_seconds)
                continue

            logger.info(
                "Soft 请求完成 %s %s status=%s success=%s %ss",
                method, url, response.status_code, payload.get("success") if isinstance(payload, dict) else "?", elapsed,
            )
            if not isinstance(payload, dict):
                raise SoftApiError("Soft 响应格式异常")
            return payload

        raise SoftApiError(last_error or "Soft 请求失败")
