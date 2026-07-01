"""账号行（含 refresh_token）→ 86 充值所需 session_info 的转换。

流程：
1. 从账号行解析 refresh_token（`rt.` 开头的字段）。
2. 用 rt 调 auth0 换取 access_token（at）。
3. 用 at 调 ChatGPT backend-api 取账号信息（me + accounts/check），curl_cffi 浏览器指纹绕过 Cloudflare。
4. 拼出标准 session_info：{accessToken, user{id,email}, account{id, planType, structure}}。

注意：refresh_token 是**轮转**的（每次换取返回新 rt，旧 rt 可能失效），因此每条只在处理开始时
转换一次；失败抛 OpenAiTokenError（卡密未消耗，安全，按单条失败跳过）。
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any

from curl_cffi import requests

logger = logging.getLogger(__name__)

# 换取端点：新版 auth.openai.com 优先，旧别名 auth0.openai.com 兜底。
_TOKEN_ENDPOINTS = ("https://auth.openai.com/oauth/token", "https://auth0.openai.com/oauth/token")
_ME_URL = "https://chatgpt.com/backend-api/me"
_CHECK_URL = "https://chatgpt.com/backend-api/accounts/check/v4-2023-04-27"


class OpenAiTokenError(RuntimeError):
    """账号行换取 token / 取账号信息失败。

    new_account_line：若 auth0 已成功（旧 rt 已轮转失效）但后续步骤失败，带回用新 rt 重建的账号行，
    供调用方持久化，避免新 rt 丢失导致账号"换不出 token"。
    """

    def __init__(self, message: str, new_account_line: str | None = None) -> None:
        super().__init__(message)
        self.new_account_line = new_account_line


def extract_refresh_token(account_line: str) -> str:
    """从账号行解析 refresh_token：取 `rt.` 开头的字段（账号行形如 邮箱----密码----xxx----rt.xxx）。"""
    s = str(account_line or "").strip()
    for part in s.split("----"):
        p = part.strip()
        if p.startswith("rt."):
            return p
    return s if s.startswith("rt.") else ""


def replace_refresh_token(account_line: str, new_rt: str) -> str:
    """把账号行里的 rt 字段替换为新 rt（其余字段保持原样）；账号行本身就是 rt 时直接返回新 rt。"""
    s = str(account_line or "").strip()
    if not new_rt:
        return s
    parts = s.split("----")
    replaced = False
    for i, part in enumerate(parts):
        if part.strip().startswith("rt."):
            parts[i] = new_rt
            replaced = True
            break
    if replaced:
        return "----".join(parts)
    return new_rt if s.startswith("rt.") else s


def looks_like_account_line(account: str) -> bool:
    """非 JSON 且含 refresh_token 的，视为账号行（需走 token 转换）。"""
    s = str(account or "").strip()
    return not s.startswith("{") and bool(extract_refresh_token(s))


def build_session_info(
    account_line: str,
    *,
    client_id: str,
    redirect_uri: str,
    proxy: str = "",
    timeout: int = 60,
    impersonate: str = "chrome",
    on_rotate: Callable[[str], None] | None = None,
) -> tuple[str, str]:
    """账号行 → (session_info JSON 字符串, 用新 rt 重建的账号行)。失败抛 OpenAiTokenError。

    on_rotate：换到新 rt 后**立即**回调（用于先把新账号行落库再继续 me/check），
    把"新 rt 丢失"的窗口压到 auth0 返回与该回调之间（无网络、极小）。
    """
    rt = extract_refresh_token(account_line)
    if not rt:
        raise OpenAiTokenError("账号缺少 refresh_token（应含 rt. 开头字段）")
    proxies = {"http": proxy, "https": proxy} if proxy else None
    to = max(1, int(timeout))

    # 1) rt -> at（成功后旧 rt 即轮转失效，必须保住返回的新 rt）
    # 两种换取方式都支持、A 不行用 B：把 (端点 × client_id) 组合依次尝试——
    # 新版(auth.openai.com + 新 client) 与旧版(auth0.openai.com + iOS client) 都覆盖。
    # invalid_client = 被拒且 rt 未消耗，可安全试下一个；成功即用。
    client_ids = [c.strip() for c in str(client_id).split(",") if c.strip()] or [str(client_id)]
    token: dict[str, Any] | None = None
    last_code = last_msg = ""
    for cid in client_ids:
        for endpoint in _TOKEN_ENDPOINTS:
            try:
                resp = requests.post(
                    endpoint,
                    json={
                        "redirect_uri": redirect_uri,
                        "grant_type": "refresh_token",
                        "client_id": cid,
                        "refresh_token": rt,
                    },
                    impersonate=impersonate,
                    proxies=proxies,
                    timeout=to,
                )
                candidate = resp.json()
            except Exception as exc:  # noqa: BLE001 - 非 JSON / 网络异常：rt 未消耗，试下一个组合
                last_msg = str(exc)
                continue
            if isinstance(candidate, dict) and candidate.get("access_token"):
                token = candidate
                break
            last_code, last_msg = _auth_error(candidate)
            # invalid_grant = rt 本身失效，换端点/client 也没用，直接放弃
            if last_code == "invalid_grant":
                break
        if token is not None or last_code == "invalid_grant":
            break
    if token is None:
        if last_code == "invalid_client":
            raise OpenAiTokenError(
                "换取 token 失败：该 rt 与所有已配置 client_id 都不匹配（invalid_client）。"
                "请补充账号来源对应的 client_id（OPENAI_OAUTH_CLIENT_ID 可逗号分隔多个）"
            )
        raise OpenAiTokenError(f"换取 token 失败：{last_msg or last_code or 'rt 无效或已失效'}")
    access_token = str(token["access_token"])
    new_rt = str(token.get("refresh_token") or "")
    new_line = replace_refresh_token(account_line, new_rt) if new_rt else str(account_line).strip()

    # 旧 rt 此刻已轮转失效：换到新 rt 后立即落库（先存再继续），避免后续步骤崩溃丢失新 rt。
    if on_rotate is not None and new_rt:
        try:
            on_rotate(new_line)
        except Exception:  # noqa: BLE001 - 回调持久化失败不阻断主流程（worker 返回后还有兜底落库）
            logger.exception("新 rt 立即落库回调失败")

    # 2) at -> 账号信息（me + accounts/check）；用 at 不消耗 rt，可重试（应对 Cloudflare 偶发拦截）。
    #    此后失败也要把新 rt 带回去，避免新 rt 丢失。
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        me = _get_json_retry(_ME_URL, headers, impersonate, proxies, to)
        check = _get_json_retry(_CHECK_URL, headers, impersonate, proxies, to)
    except OpenAiTokenError as exc:
        exc.new_account_line = new_line
        raise
    if not isinstance(me, dict) or not me.get("id"):
        raise OpenAiTokenError("获取账号信息失败：me 返回异常（账号可能异常或被风控）", new_account_line=new_line)

    account = _pick_account(check)

    session = {
        "accessToken": access_token,
        "user": {"id": str(me.get("id") or ""), "email": str(me.get("email") or "")},
        "account": {
            "id": str(account.get("account_id") or ""),
            "planType": str(account.get("plan_type") or "free"),
            "structure": str(account.get("structure") or "personal"),
        },
    }
    return json.dumps(session, ensure_ascii=False), new_line


def _auth_error(token: Any) -> tuple[str, str]:
    """解析 auth0 token 错误响应 → (code, message)，兼容 {"error":{...}} 与 {"error":"..."} 两种形态。"""
    if not isinstance(token, dict):
        return "", ""
    err = token.get("error")
    if isinstance(err, dict):
        return str(err.get("code") or ""), str(err.get("message") or "")
    if isinstance(err, str):
        return err, str(token.get("error_description") or "")
    return "", ""


_IMPERSONATE_FALLBACKS = ("chrome", "chrome124", "safari17_0", "chrome110", "edge101")


def _get_json_retry(url: str, headers: dict, impersonate: str, proxies, timeout: int, attempts: int = 3) -> Any:
    """GET 并解析 JSON。用 at 不消耗 rt，可重试；每次轮换浏览器指纹以尽量绕过 Cloudflare 风控。"""
    imps = [impersonate, *[i for i in _IMPERSONATE_FALLBACKS if i != impersonate]]
    tries = max(attempts, len(imps))
    last = ""
    blocked = False
    for i in range(tries):
        imp = imps[i % len(imps)]
        try:
            resp = requests.get(url, headers=headers, impersonate=imp, proxies=proxies, timeout=timeout)
            text = resp.text or ""
            # 403/429 或返回 HTML（挑战页）= 被风控拦截，换指纹重试。
            if resp.status_code in (403, 429) or text.lstrip()[:1] == "<":
                blocked = True
                last = f"HTTP {resp.status_code} 疑似风控拦截"
                time.sleep(1.5)
                continue
            return resp.json()
        except Exception as exc:  # noqa: BLE001 - 非 JSON 或网络异常
            last = str(exc)
            time.sleep(1.5)
    hint = "（疑似 Cloudflare 风控，建议配置代理 ASKWHY_REQUEST_PROXY 或更换出口 IP）" if blocked else ""
    raise OpenAiTokenError(f"获取账号信息失败：{last}{hint}")


def _pick_account(check: Any) -> dict[str, Any]:
    """从 accounts/check 选出账号：优先 personal。"""
    accounts = check.get("accounts") if isinstance(check, dict) else None
    if not isinstance(accounts, dict):
        return {}
    fallback: dict[str, Any] = {}
    for value in accounts.values():
        acc = value.get("account") if isinstance(value, dict) else None
        if not isinstance(acc, dict):
            continue
        if not fallback:
            fallback = acc
        if acc.get("structure") == "personal":
            return acc
    return fallback
