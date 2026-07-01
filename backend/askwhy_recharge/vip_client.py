"""74 渠道（zzlokp12）上游客户端（出站走 curl_cffi，与仓库其他出站调用一致）。

统一在 base_url + api_prefix（默认 /api）下：
- POST vip/c    {cdk, account}   验证卡密（code 1 通过 / 0 失败）
- POST vip/r    {cdk, account}   充值（code 1 成功 / 0 失败）
- POST vip/cdks ["卡","卡"]       批量查询卡密状态（data[].useStatus: not_used/used）

返回上游原始 JSON（含 code 字段），由调用方判断业务结果；网络/解析异常抛 VipApiError。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

from curl_cffi import requests

logger = logging.getLogger(__name__)


class VipApiError(RuntimeError):
    """74 渠道接口调用异常（网络/解析层面）。"""


@dataclass
class VipClient:
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
            raise VipApiError("缺少 VIP_BASE_URL")

    # ---- 业务接口 ----
    def verify(self, cdk: str, account: str) -> dict[str, Any]:
        return self._request("POST", "vip/c", json={"cdk": cdk, "account": account})

    def recharge(self, cdk: str, account: str) -> dict[str, Any]:
        # 充值非幂等：失败不重试，避免同一卡密重复提交。
        return self._request("POST", "vip/r", attempts=1, json={"cdk": cdk, "account": account})

    def query_cdks(self, cdks: list[str]) -> dict[str, Any]:
        # 请求体为原始 JSON 数组。
        return self._request("POST", "vip/cdks", json=list(cdks))

    # ---- 内部 ----
    def _request(self, method: str, path: str, attempts: int | None = None, **kwargs: Any) -> dict[str, Any]:
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
                logger.warning("VIP 请求异常 %s %s attempt=%s/%s err=%s", method, url, attempt, total, exc)
                if attempt < total:
                    time.sleep(self.retry_interval_seconds)
                continue

            elapsed = round(time.monotonic() - started, 3)
            try:
                payload = response.json()
            except Exception:  # noqa: BLE001 - 非 JSON 响应
                last_error = f"HTTP {response.status_code} 非 JSON 响应"
                logger.warning("VIP 响应非 JSON %s %s status=%s", method, url, response.status_code)
                if attempt < total:
                    time.sleep(self.retry_interval_seconds)
                continue

            logger.info(
                "VIP 请求完成 %s %s status=%s code=%s %ss",
                method, url, response.status_code, payload.get("code") if isinstance(payload, dict) else "?", elapsed,
            )
            if not isinstance(payload, dict):
                raise VipApiError("VIP 响应格式异常")
            return payload

        raise VipApiError(last_error or "VIP 请求失败")
