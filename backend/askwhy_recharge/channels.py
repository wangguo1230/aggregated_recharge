"""渠道适配层：把不同上游（86GPT / 74）的协议差异收敛成统一的 Outcome，
批量引擎只面向 Outcome.kind 决策，不关心具体上游。

新增渠道 = 实现一个 adapter（submit / confirm / recheck）并注册即可。
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .gift_client import GiftApiError, GiftClient
from .openai_token import OpenAiTokenError, build_session_info, extract_refresh_token
from .settings import AskWhySettings
from .soft_client import SoftApiError, SoftClient
from .vip_client import VipApiError, VipClient

logger = logging.getLogger(__name__)

CHANNELS = ("gpt86", "vip74", "soft")
CHANNEL_LABELS = {"gpt86": "86GPT", "vip74": "74渠道", "soft": "软件订阅"}

# 86GPT（Gift）稳定 code 分档。
_GPT86_TRANSIENT_CODES = frozenset({"stock.out_of_stock", "activation.cooldown", "provider.temporary_error"})
_GPT86_SYSTEMIC_CODES = frozenset({"server.internal_error"})
# 74 渠道无稳定 code，只能按 message 关键字判断「可重试」（缺货/限流/繁忙/维护）。
_VIP_TRANSIENT_KEYWORDS = ("库存", "缺货", "稍后", "繁忙", "频繁", "限流", "维护", "暂时", "排队")
# 软件订阅渠道：仅「无可用充值凭证」视为可重试（凭证不足），其余 code 为单条失败。
_SOFT_TRANSIENT_CODES = frozenset({"NO_AVAILABLE_CREDENTIAL"})


class ProviderUnknownError(RuntimeError):
    """提交结果未知（网络/解析异常）：禁止自动重试，转人工确认。"""


class AccountPrepareError(RuntimeError):
    """提交前的账号准备失败（如账号行 rt 换取 token 失败）：卡密未消耗，按单条失败跳过。

    updated_account_line：若 rt 已轮转出新值（旧 rt 失效），带回供持久化，避免新 rt 丢失。
    """

    def __init__(self, message: str, updated_account_line: str | None = None) -> None:
        super().__init__(message)
        self.updated_account_line = updated_account_line


@dataclass
class Outcome:
    """统一结果：kind ∈ success / processing / transient / item_fail / systemic。"""

    kind: str
    code: str = ""
    message: str = ""
    account: str = ""
    completed_at: str = ""
    use_status: int | None = None
    snapshot: dict[str, Any] | None = None


# ==================== 通用工具 ====================
def _extract_data(parsed: Any) -> dict[str, Any]:
    """取账号数据对象：兼容已包裹的 platformCredential（{platform,data}）与裸账号 JSON。"""
    if isinstance(parsed, dict):
        if "data" in parsed and "platform" in parsed and isinstance(parsed["data"], dict):
            return parsed["data"]
        return parsed
    return {}


def parse_email(account: str) -> str:
    """解析账号邮箱：JSON 取 user.email（兼容包裹结构）；账号行取含 @ 的字段；失败返回空。"""
    s = str(account or "").strip()
    try:
        data = _extract_data(json.loads(s))
        if isinstance(data.get("user"), dict):
            email = data["user"].get("email")
            if isinstance(email, str) and email:
                return email.strip()[:255]
    except (ValueError, TypeError):
        pass
    for part in s.split("----"):
        p = part.strip()
        if "@" in p and "." in p:
            return p[:255]
    return ""


def validate_account(channel: str, account: str) -> bool:
    """提交前的本地校验，避免把卡密浪费在垃圾输入上。

    - gpt86：含 accessToken 的 JSON（session_info），或含 refresh_token 的账号行。
    - soft：含 accessToken 的 JSON 对象（兼容包裹结构）。
    - vip74：账号格式未知，仅要求是非空 JSON 对象。
    """
    s = str(account or "").strip()
    if channel == "gpt86":
        if s.startswith("{"):
            try:
                return bool(_extract_data(json.loads(s)).get("accessToken"))
            except (ValueError, TypeError):
                return False
        return bool(extract_refresh_token(s))
    try:
        parsed = json.loads(s)
    except (ValueError, TypeError):
        return False
    if not isinstance(parsed, dict) or not parsed:
        return False
    if channel == "soft":
        return bool(_extract_data(parsed).get("accessToken"))
    return True


# ==================== 86GPT（Gift）适配器 ====================
class Gpt86Adapter:
    code = "gpt86"

    def __init__(self, client: GiftClient, settings: AskWhySettings) -> None:
        self.client = client
        self.settings = settings

    def prepare(self, account: str, on_rotate: Callable[[str], None] | None = None) -> tuple[str, str | None]:
        """返回 (提交用 account, 需回写的新账号行|None)。

        账号为 JSON(session_info) 直接用；为账号行(含 rt) 则 rt→at→拼 session_info（一次性）。
        on_rotate：换到新 rt 后立即落库（消除崩溃丢新 rt 的窗口）。
        """
        s = str(account or "").strip()
        if s.startswith("{") or not extract_refresh_token(s):
            return account, None
        try:
            session_info, new_line = build_session_info(
                s,
                client_id=self.settings.openai_oauth_client_id,
                redirect_uri=self.settings.openai_oauth_redirect_uri,
                proxy=self.settings.request_proxy,
                timeout=self.settings.request_timeout_seconds,
                impersonate=self.settings.openai_impersonate,
                on_rotate=on_rotate,
            )
        except OpenAiTokenError as exc:
            raise AccountPrepareError(str(exc), updated_account_line=getattr(exc, "new_account_line", None)) from exc
        return session_info, new_line

    def submit(self, cdk: str, account: str, force: bool) -> Outcome:
        try:
            res = self.client.activate_session(cdk, account, force=force)
        except GiftApiError as exc:
            raise ProviderUnknownError(str(exc)) from exc
        return self._classify(res)

    def _classify(self, res: dict[str, Any]) -> Outcome:
        success = bool(res.get("success"))
        data = res.get("data") if isinstance(res.get("data"), dict) else {}
        raw = data.get("use_status")
        use = int(raw) if isinstance(raw, (int, float)) else None
        code = str(res.get("code") or data.get("status_code") or "")
        msg = str(res.get("msg") or "")
        account = str(data.get("account") or "")
        completed = str(data.get("completed_at") or "")
        if use == -9 or code in _GPT86_TRANSIENT_CODES:
            return Outcome("transient", code, msg, use_status=use)
        if success and use == 1:
            return Outcome("success", code, msg, account, completed, use)
        if use == -1:
            return Outcome("processing", code, msg, account, completed, use)
        if code in _GPT86_SYSTEMIC_CODES:
            return Outcome("systemic", code, msg, account, completed, use)
        return Outcome("item_fail", code, msg, account, completed, use)

    def recheck(self, cdk: str) -> Outcome:
        """处理中(-1) 的有限次到账复查。"""
        attempts = max(1, self.settings.batch_recheck_attempts)
        interval = self.settings.batch_recheck_interval_seconds
        use: int | None = -1
        account = completed = ""
        snapshot: dict[str, Any] = {}
        for _ in range(attempts):
            if interval > 0:
                time.sleep(interval)
            snapshot = self.confirm(cdk)
            current = snapshot.get("useStatus") if snapshot else None
            current = int(current) if isinstance(current, (int, float)) else None
            if current is not None:
                use = current
                account = snapshot.get("account") or account
                completed = snapshot.get("completedAt") or completed
            if current == 1:
                return Outcome("success", "", "", account, completed, current, snapshot)
            if current is not None and current not in (-1, 0):
                return Outcome("item_fail", "", "", account, completed, current, snapshot)
        return Outcome("processing", "", "", account, completed, use, snapshot)

    def confirm(self, cdk: str) -> dict[str, Any]:
        try:
            res = self.client.check(cdk)
        except GiftApiError:
            return {}
        data = res.get("data") if isinstance(res.get("data"), dict) else {}
        return {
            "useStatus": data.get("use_status"),
            "account": str(data.get("account") or ""),
            "completedAt": str(data.get("completed_at") or ""),
            "statusHint": str(data.get("status_hint") or ""),
            "giftName": str(data.get("gift_name") or ""),
        }


# ==================== 74 渠道（zzlokp12）适配器 ====================
class Vip74Adapter:
    code = "vip74"

    def __init__(self, client: VipClient, settings: AskWhySettings) -> None:
        self.client = client
        self.settings = settings

    def prepare(self, account: str, on_rotate: Callable[[str], None] | None = None) -> tuple[str, str | None]:  # noqa: ARG002
        return account, None

    def submit(self, cdk: str, account: str, force: bool) -> Outcome:  # noqa: ARG002 - 74 无 force
        try:
            res = self.client.recharge(cdk, account)
        except VipApiError as exc:
            raise ProviderUnknownError(str(exc)) from exc
        code = res.get("code")
        msg = str(res.get("message") or "")
        if code == 1:
            return Outcome("success", "vip.ok", msg or "充值成功")
        # code 0：按 message 关键字判断是否可重试（缺货/限流等），否则单条失败。
        if any(k in msg for k in _VIP_TRANSIENT_KEYWORDS):
            return Outcome("transient", "vip.transient", msg or "暂不可用，等待重试")
        return Outcome("item_fail", "vip.fail", msg or "充值失败")

    def recheck(self, cdk: str) -> Outcome:  # 74 无「处理中」态，不会被调用
        return Outcome("processing")

    def confirm(self, cdk: str) -> dict[str, Any]:
        try:
            res = self.client.query_cdks([cdk])
        except VipApiError:
            return {}
        rows = res.get("data") if isinstance(res.get("data"), list) else []
        row = rows[0] if rows else {}
        return {
            "useStatus": row.get("useStatus"),  # not_used / used
            "usedAt": str(row.get("usedAt") or ""),
            "carmi": str(row.get("carmi") or ""),
        }


# ==================== 软件订阅渠道（ChatGPT 兑换 API）适配器 ====================
class SoftAdapter:
    code = "soft"

    def __init__(self, client: SoftClient, settings: AskWhySettings) -> None:
        self.client = client
        self.settings = settings

    def prepare(self, account: str, on_rotate: Callable[[str], None] | None = None) -> tuple[str, str | None]:  # noqa: ARG002
        return account, None

    def submit(self, cdk: str, account: str, force: bool) -> Outcome:  # noqa: ARG002 - soft 无 force
        try:
            credential = _extract_data(json.loads(account))
        except (ValueError, TypeError):
            return Outcome("item_fail", "input.account_invalid", "账号 JSON 无法解析")
        try:
            # 确认即实际兑换（内部会再校验 CDK 与账号）。
            res = self.client.confirm(cdk, credential)
        except SoftApiError as exc:
            raise ProviderUnknownError(str(exc)) from exc
        if res.get("success"):
            return Outcome("success", "", "兑换成功")
        error = res.get("error") if isinstance(res.get("error"), dict) else {}
        code = str(error.get("code") or "")
        message = str(error.get("message") or "兑换失败")
        if code in _SOFT_TRANSIENT_CODES:
            return Outcome("transient", code, message)
        return Outcome("item_fail", code, message)

    def recheck(self, cdk: str) -> Outcome:  # soft 无「处理中」态，不会被调用
        return Outcome("processing")

    def confirm(self, cdk: str) -> dict[str, Any]:  # soft 无独立查询接口，确认成功即到账
        return {}


# ==================== 注册表 ====================
_adapters: dict[str, Any] = {}


def configure_channels(
    gift_client: GiftClient,
    vip_client: VipClient,
    soft_client: SoftClient,
    settings: AskWhySettings,
) -> None:
    _adapters["gpt86"] = Gpt86Adapter(gift_client, settings)
    _adapters["vip74"] = Vip74Adapter(vip_client, settings)
    _adapters["soft"] = SoftAdapter(soft_client, settings)


def get_adapter(channel: str):
    return _adapters.get(channel)
