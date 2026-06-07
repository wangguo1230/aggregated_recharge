"""敏感数据处理工具（加密与指纹）。

独立工程自带实现，仅依赖 cryptography，不引入外部业务包。
"""

from __future__ import annotations

import hashlib
import hmac
from base64 import urlsafe_b64encode

from cryptography.fernet import Fernet, InvalidToken


class AskWhyCryptoError(RuntimeError):
    """敏感数据处理异常。"""


def hmac_sha256(value: str, secret: str) -> str:
    secret_value = str(secret or "").encode("utf-8")
    if not secret_value:
        raise AskWhyCryptoError("缺少 ASKWHY_SECRET_KEY，无法计算 HMAC")
    return hmac.new(secret_value, str(value or "").encode("utf-8"), hashlib.sha256).hexdigest()


def fingerprint(value: str, secret: str) -> str:
    """对敏感值生成不可逆指纹，供检索/去重（不泄露原文）。"""

    return hmac_sha256(str(value or "").strip(), secret)[:16]


class FernetSecretCipher:
    """基于 Fernet 的对称加密器，密钥由 secret_key 派生。"""

    def __init__(self, secret_key: str) -> None:
        raw = str(secret_key or "").strip()
        if not raw:
            raise AskWhyCryptoError("缺少 ASKWHY_SECRET_KEY，无法初始化加密器")
        key = urlsafe_b64encode(hashlib.sha256(raw.encode("utf-8")).digest())
        self._fernet = Fernet(key)

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(str(value or "").encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(str(value or "").encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise AskWhyCryptoError("敏感字段解密失败") from exc
