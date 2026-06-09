"""外部码（对客户暴露的卡密）生成与归一化。

外部码不含任何套餐类型信息，形如 AW-XXXXX-XXXXX（Crockford base32，去除易混字符）。
归一化用于查找：去掉分隔符并大写。
"""

from __future__ import annotations

import re
import secrets

# Crockford base32，去掉 I L O U 等易混字符。
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_BODY_LEN = 10
_PREFIX = "AW"


def normalize_external_code(code: str) -> str:
    """去除非字母数字并大写，作为唯一查找键。"""

    return re.sub(r"[^A-Za-z0-9]+", "", str(code or "")).upper()


def _random_body() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(_BODY_LEN))


def generate_external_code(prefix: str = _PREFIX) -> tuple[str, str]:
    """生成 (展示码, 归一化码)。展示码带分隔符便于阅读。

    prefix 区分业务线（充值卡用 AW，接码卡用 SM），不影响归一化查找逻辑。
    """

    body = _random_body()
    display = f"{prefix}-{body[:5]}-{body[5:]}"
    return display, normalize_external_code(display)
