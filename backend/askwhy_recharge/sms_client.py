"""接码短信查询客户端（出站走 curl_cffi，与仓库其他出站调用一致）。

接码卡密形如 `手机号----查询URL`（例：`13527097093----https://api.k8sms.com/q/<token>`）。
查询 URL 自带鉴权 token，直接 GET 即可，返回纯文本：
- 无短信：形如「没有获取到有效短信，过期时间：2026-07-08 14:34:00」
- 有短信：短信全文（含验证码）

URL 绝不暴露给客户端：仅后端解密后用于出站请求。
"""

from __future__ import annotations

import logging
import re
import time

from curl_cffi import requests

logger = logging.getLogger(__name__)

# 真实接码卡密中手机号与查询 URL 的分隔符。
CARD_SEPARATOR = "----"

# 判定「尚未收到短信」的文案标志（保守匹配，避免误伤含数字日期的成功短信）。
_NO_SMS_MARKERS = ("没有获取到", "未获取到", "暂无短信", "无有效短信", "无短信")

# 验证码候选：连续 4~8 位数字（短信正文中最常见的验证码形态）。
# 用前后断言排除被日期/时间分隔符（- : /）紧邻的数字段，避免把短信前缀时间戳
# 中的年份/日期（如 [2026-06-09 21:35:10] 的 2026）误当成验证码。
_CODE_PATTERN = re.compile(r"(?<![\d/:-])\d{4,8}(?![\d/:-])")


class SmsApiError(RuntimeError):
    """接码查询异常（网络/解析层面）。"""


def split_card(real_card: str) -> tuple[str, str]:
    """拆解真实接码卡密为 (手机号, 查询URL)；格式非法返回 ("", "")。"""

    text = str(real_card or "").strip()
    if CARD_SEPARATOR not in text:
        return "", ""
    phone, _, url = text.partition(CARD_SEPARATOR)
    return phone.strip(), url.strip()


def fetch_sms_text(
    url: str,
    *,
    proxy: str = "",
    timeout: int = 30,
    retry_attempts: int = 2,
    retry_interval_seconds: float = 1.5,
) -> str:
    """GET 查询 URL，返回响应纯文本；网络异常重试后抛 SmsApiError。"""

    target = str(url or "").strip()
    if not target:
        raise SmsApiError("接码查询 URL 为空")
    proxies = {"http": proxy, "https": proxy} if proxy else None
    attempts = max(1, int(retry_attempts))
    last_error = ""
    for attempt in range(1, attempts + 1):
        started = time.monotonic()
        try:
            response = requests.get(
                target,
                headers={"Accept": "*/*"},
                proxies=proxies,
                timeout=max(1, int(timeout)),
            )
        except Exception as exc:  # noqa: BLE001 - curl_cffi 抛出多种网络异常
            last_error = str(exc)
            logger.warning("接码请求异常 attempt=%s/%s err=%s", attempt, attempts, exc)
            if attempt < attempts:
                time.sleep(retry_interval_seconds)
            continue
        elapsed = round(time.monotonic() - started, 3)
        logger.info("接码请求完成 status=%s %ss", response.status_code, elapsed)
        return response.text or ""
    raise SmsApiError(last_error or "接码查询失败")


def parse_sms(text: str) -> dict:
    """解析接码响应文本，返回 {hasSms, code, content}。

    先判定无短信文案（其文本含到期日期数字，必须优先排除），再提取验证码。
    """

    content = str(text or "").strip()
    has_sms = bool(content) and not any(marker in content for marker in _NO_SMS_MARKERS)
    code = ""
    if has_sms:
        match = _CODE_PATTERN.search(content)
        code = match.group(0) if match else ""
    return {"hasSms": has_sms, "code": code, "content": content}
