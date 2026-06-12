"""AskWhy 充值 ORM 模型。

- AskWhyOrderModel：每次充值的真实卡密与 Session JSON（均加密存储）、AskWhy 订单号、
  状态与订阅快照，便于事后对账与售后；额外记录提交时使用的外部码。
- AskWhyCardMappingModel：外部码 ↔ 真实 AskWhy 卡密映射（真实卡加密存储）。
- SmsCardMappingModel：外部码（兑换码）↔ 接码卡密（手机号----查询URL）映射；
  整串加密存储，手机号另存明文列供展示与检索，查询 URL 绝不暴露给客户端。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class AskWhyOrderModel(Base):
    __tablename__ = "askwhy_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # AskWhy 返回的订单 ID，作为后续状态/订阅查询的主键。
    askwhy_order_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)

    # 敏感字段：加密存储，不落明文。fingerprint 供检索/去重。
    card_code_encrypted: Mapped[str] = mapped_column(Text, default="")
    card_fingerprint: Mapped[str] = mapped_column(String(80), default="", index=True)
    card_last4: Mapped[str] = mapped_column(String(8), default="")
    fetch_token_encrypted: Mapped[str] = mapped_column(Text, default="")

    # 提交时使用的外部码（便于按外部码追溯订单）。
    external_code: Mapped[str] = mapped_column(String(64), default="", index=True)

    card_type: Mapped[str] = mapped_column(String(40), default="")
    card_type_label: Mapped[str] = mapped_column(String(80), default="")

    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    result_message: Mapped[str] = mapped_column(Text, default="")
    request_type: Mapped[str] = mapped_column(String(40), default="")
    account_email: Mapped[str] = mapped_column(String(255), default="", index=True)
    account_id: Mapped[str] = mapped_column(String(120), default="")

    subscription_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    submit_ip: Mapped[str] = mapped_column(String(80), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AskWhyCardMappingModel(Base):
    __tablename__ = "askwhy_card_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 对客户暴露的外部码：display 为展示形（带分隔符），norm 为归一化唯一键。
    external_code: Mapped[str] = mapped_column(String(64), default="")
    external_code_norm: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # 真实 AskWhy 卡密：加密存储，fingerprint 用于去重（避免同一真实卡重复映射）。
    real_card_encrypted: Mapped[str] = mapped_column(Text, default="")
    real_card_fingerprint: Mapped[str] = mapped_column(String(80), default="", index=True)
    real_card_last4: Mapped[str] = mapped_column(String(8), default="")

    # 录入时校验得到的套餐信息（仅管理端展示，外部码本身不含类型）。
    card_type: Mapped[str] = mapped_column(String(40), default="")
    card_type_label: Mapped[str] = mapped_column(String(80), default="")

    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    note: Mapped[str] = mapped_column(String(255), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class SmsCardMappingModel(Base):
    __tablename__ = "sms_card_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 对客户暴露的兑换码：display 带分隔符（前缀 SM），norm 为归一化唯一键。
    external_code: Mapped[str] = mapped_column(String(64), default="")
    external_code_norm: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # 真实接码卡密（手机号----查询URL）：整串加密，fingerprint 用于去重。
    real_card_encrypted: Mapped[str] = mapped_column(Text, default="")
    real_card_fingerprint: Mapped[str] = mapped_column(String(80), default="", index=True)

    # 手机号明文存储：需展示给客户并支持管理端检索；查询 URL 仅在加密串中、不单独落明文。
    phone: Mapped[str] = mapped_column(String(40), default="", index=True)

    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    note: Mapped[str] = mapped_column(String(255), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ClaudeCardMappingModel(Base):
    """外部码 ↔ 真实 Gift cdkey 映射（Claude Pro 充值，真实 cdkey 加密存储）。"""

    __tablename__ = "claude_card_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 对客户暴露的外部码：display 带分隔符（前缀 CL），norm 为归一化唯一键。
    external_code: Mapped[str] = mapped_column(String(64), default="")
    external_code_norm: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # 真实 Gift cdkey：加密存储，fingerprint 用于去重（避免同一真实卡重复映射）。
    real_card_encrypted: Mapped[str] = mapped_column(Text, default="")
    real_card_fingerprint: Mapped[str] = mapped_column(String(80), default="", index=True)
    real_card_last4: Mapped[str] = mapped_column(String(8), default="")

    # 录入时 check 得到的商品信息（仅管理端展示）。
    gift_name: Mapped[str] = mapped_column(String(80), default="")
    app: Mapped[str] = mapped_column(String(20), default="claude")

    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    note: Mapped[str] = mapped_column(String(255), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ClaudeOrderModel(Base):
    """Claude Pro 充值记录：真实 cdkey 加密存储，记录客户提交的 uid、状态与结果，便于对账与售后。"""

    __tablename__ = "claude_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 敏感字段：真实 cdkey 加密存储；fingerprint 供检索。
    card_code_encrypted: Mapped[str] = mapped_column(Text, default="")
    card_fingerprint: Mapped[str] = mapped_column(String(80), default="", index=True)
    card_last4: Mapped[str] = mapped_column(String(8), default="")

    # 提交时使用的外部码、客户提交的 Claude Organization ID（uid，明文供展示/检索）。
    external_code: Mapped[str] = mapped_column(String(64), default="", index=True)
    uid: Mapped[str] = mapped_column(String(120), default="", index=True)

    gift_name: Mapped[str] = mapped_column(String(80), default="")
    # use_status：0待提交 / -1处理中 / 1已完成 / -9库存不足 / -999异常 / -1000已作废 / -1001售后
    use_status: Mapped[int] = mapped_column(Integer, default=0, index=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    result_message: Mapped[str] = mapped_column(Text, default="")
    account: Mapped[str] = mapped_column(String(255), default="")
    completed_at: Mapped[str] = mapped_column(String(40), default="")
    submit_ip: Mapped[str] = mapped_column(String(80), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
