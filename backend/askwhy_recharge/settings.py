"""AskWhy 充值服务运行配置。

全部来自环境变量（或 backend 目录下的 .env），系统环境变量优先级更高。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from . import PROJECT_ROOT

_INSECURE_SECRET_KEY_VALUES = {
    "",
    "dev-askwhy-secret-change-me",
    "change-me-before-production",
}
_INSECURE_ADMIN_TOKEN_VALUES = {
    "change-me-admin-token",
    "请填写强随机口令",
}
_ADMIN_TOKEN_MIN_LEN = 16


def _load_local_env() -> None:
    """加载 backend 目录下 .env，已存在的系统环境变量不会被覆盖。"""

    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int, *, minimum: int = 1) -> int:
    try:
        return max(minimum, int(str(os.environ.get(name, default)).strip()))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class AskWhySettings:
    database_url: str
    secret_key: str
    admin_token: str = ""
    askwhy_base_url: str = "https://askwhy123.shop"
    askwhy_api_prefix: str = "/api"
    # Gift 提交页上游（Claude Pro 充值走此通道）
    gift_base_url: str = "https://gpt.86gamestore.com"
    gift_api_prefix: str = "/api"
    request_timeout_seconds: int = 60
    request_retry_attempts: int = 2
    request_proxy: str = ""
    cors_allow_origins: tuple[str, ...] = ("*",)
    host: str = "0.0.0.0"
    port: int = 18424
    allow_insecure_defaults: bool = False


def load_askwhy_settings() -> AskWhySettings:
    _load_local_env()

    database_url = str(os.environ.get("ASKWHY_DATABASE_URL") or "").strip()
    if not database_url:
        raise RuntimeError("缺少 ASKWHY_DATABASE_URL")

    secret_key = str(os.environ.get("ASKWHY_SECRET_KEY") or "").strip()
    allow_insecure = _truthy(os.environ.get("ASKWHY_ALLOW_INSECURE_DEFAULTS"))
    if secret_key in _INSECURE_SECRET_KEY_VALUES and not allow_insecure:
        raise RuntimeError("缺少安全的 ASKWHY_SECRET_KEY，无法加密落库")

    admin_token = str(os.environ.get("ASKWHY_ADMIN_TOKEN") or "").strip()
    # 空 = 管理接口禁用（fail-closed）。一旦配置，拒绝占位值与过短口令，除非显式放行。
    if admin_token and not allow_insecure:
        if admin_token in _INSECURE_ADMIN_TOKEN_VALUES or len(admin_token) < _ADMIN_TOKEN_MIN_LEN:
            raise RuntimeError(
                f"ASKWHY_ADMIN_TOKEN 过弱（需 ≥{_ADMIN_TOKEN_MIN_LEN} 位且非占位值）"
            )

    cors_raw = str(os.environ.get("ASKWHY_CORS_ALLOW_ORIGINS", "*")).strip()
    cors_origins = tuple(item.strip() for item in cors_raw.split(",") if item.strip()) or ("*",)

    return AskWhySettings(
        database_url=database_url,
        secret_key=secret_key,
        admin_token=admin_token,
        askwhy_base_url=str(os.environ.get("ASKWHY_BASE_URL", "https://askwhy123.shop")).strip().rstrip("/")
        or "https://askwhy123.shop",
        askwhy_api_prefix=str(os.environ.get("ASKWHY_API_PREFIX", "/api")).strip() or "/api",
        gift_base_url=str(os.environ.get("GIFT_BASE_URL", "https://gpt.86gamestore.com")).strip().rstrip("/")
        or "https://gpt.86gamestore.com",
        gift_api_prefix=str(os.environ.get("GIFT_API_PREFIX", "/api")).strip() or "/api",
        request_timeout_seconds=_int_env("ASKWHY_REQUEST_TIMEOUT", 60),
        request_retry_attempts=_int_env("ASKWHY_REQUEST_RETRY", 2),
        request_proxy=str(os.environ.get("ASKWHY_REQUEST_PROXY", "")).strip(),
        cors_allow_origins=cors_origins,
        host=str(os.environ.get("ASKWHY_HOST", "0.0.0.0")).strip() or "0.0.0.0",
        port=_int_env("ASKWHY_PORT", 18424),
        allow_insecure_defaults=allow_insecure,
    )
