"""AskWhy 充值 ORM 模型。

- AskWhyOrderModel：每次充值的真实卡密与 Session JSON（均加密存储）、AskWhy 订单号、
  状态与订阅快照，便于事后对账与售后；额外记录提交时使用的外部码。
- AskWhyCardMappingModel：外部码 ↔ 真实 AskWhy 卡密映射（真实卡加密存储）。
- SmsCardMappingModel：外部码（兑换码）↔ 接码卡密（手机号----查询URL）映射；
  整串加密存储，手机号另存明文列供展示与检索，查询 URL 绝不暴露给客户端。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
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

class GptOrderModel(Base):
    """GPT 充值记录：直接调用 Gift 上游（无外部码映射），客户提交真实 cdkey + Session JSON。

    真实 cdkey 与 Session JSON 均加密存储；记录状态/结果/账号邮箱，便于对账与售后。
    """

    __tablename__ = "gpt_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 渠道：gpt86（86GPT/Gift）/ vip74（74 渠道）。
    channel: Mapped[str] = mapped_column(String(20), default="gpt86", index=True)
    # 敏感字段：真实 cdkey 与 Session JSON 加密存储；fingerprint 供检索/去重。
    card_code_encrypted: Mapped[str] = mapped_column(Text, default="")
    card_fingerprint: Mapped[str] = mapped_column(String(80), default="", index=True)
    card_last4: Mapped[str] = mapped_column(String(8), default="")
    session_info_encrypted: Mapped[str] = mapped_column(Text, default="")

    gift_name: Mapped[str] = mapped_column(String(80), default="")
    # use_status：0待提交 / -1处理中 / 1已完成 / -9库存不足 / -999异常 / -1000已作废 / -1001售后
    use_status: Mapped[int] = mapped_column(Integer, default=0, index=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    result_message: Mapped[str] = mapped_column(Text, default="")
    # GPT 充值成功后上游返回的账号邮箱。
    account: Mapped[str] = mapped_column(String(255), default="", index=True)
    completed_at: Mapped[str] = mapped_column(String(40), default="")
    submit_ip: Mapped[str] = mapped_column(String(80), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class GptBatchModel(Base):
    """GPT 批量订阅任务：管理员上传一批 (cdkey + Session JSON)，后台串行逐条订阅。

    状态机：PENDING(已建/待执行) → RUNNING(执行中) → DONE / CANCELLED。
    计数（成功/失败/处理中等）按需从 gpt_batch_items 聚合，不在本表冗余存储，避免漂移。
    """

    __tablename__ = "gpt_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 渠道：gpt86（86GPT/Gift）/ vip74（74 渠道 zzlokp12）。
    channel: Mapped[str] = mapped_column(String(20), default="gpt86", index=True)
    # 状态：PENDING / RUNNING / PAUSED(遇错暂停，待人工继续或取消) / DONE / CANCELLED。
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    # force=True 时所有条目提交带 force=1（跳过套餐检查）。
    force: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str] = mapped_column(String(255), default="")
    total: Mapped[int] = mapped_column(Integer, default=0)
    # 取消标记：执行线程在每条之间读取该值，置位后停止并把剩余条目标记 SKIPPED。
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)

    # 批内并发数（同时处理多少条），默认 1（串行）。
    concurrency: Mapped[int] = mapped_column(Integer, default=1)
    paused_reason: Mapped[str] = mapped_column(String(255), default="")  # 暂停原因（PAUSED 时）

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class GptBatchItemModel(Base):
    """GPT 批量订阅条目：每条 = 一张 cdkey + 一个账号 Session。

    cdkey 与 Session JSON 均加密存储；email 解析自 Session 明文存储（展示/检索用）。
    状态机：
    - PENDING       待处理（仅此状态会被执行线程认领）
    - SUBMITTING    已原子认领、提交中（崩溃后续跑视为疑似已提交 → NEEDS_REVIEW）
    - SUCCEEDED     上游 use_status=1，且到账确认通过
    - PROCESSING    上游 use_status=-1，复查后仍未到账（可事后再查）
    - FAILED        上游明确拒绝（终态）
    - SKIPPED       未提交即跳过（批内重复 / Session 非法 / cdkey 已用过 / 任务取消）
    - NEEDS_REVIEW  提交后结果未知（网络异常 / 中断），禁止自动重试，需人工核对
    """

    __tablename__ = "gpt_batch_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    batch_id: Mapped[int] = mapped_column(Integer, index=True)
    # 渠道冗余存储（来自所属批次），便于按渠道做卡密去重查询。
    channel: Mapped[str] = mapped_column(String(20), default="gpt86", index=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)

    # 敏感字段加密存储；fingerprint 供去重与「卡密是否已用过」判定。
    cdkey_encrypted: Mapped[str] = mapped_column(Text, default="")
    cdkey_fingerprint: Mapped[str] = mapped_column(String(80), default="", index=True)
    cdkey_last4: Mapped[str] = mapped_column(String(8), default="")
    session_info_encrypted: Mapped[str] = mapped_column(Text, default="")
    session_fingerprint: Mapped[str] = mapped_column(String(80), default="", index=True)
    # 实际提交给上游的内容（86 账号行模式 = 拼接好的 session_info；其他 = 提交的账号），加密存储。
    built_session_encrypted: Mapped[str] = mapped_column(Text, default="")
    # 从 Session JSON 解析出的账号邮箱（明文，供展示/检索）。
    email: Mapped[str] = mapped_column(String(255), default="", index=True)

    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    use_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_code: Mapped[str] = mapped_column(String(64), default="")
    result_message: Mapped[str] = mapped_column(Text, default="")
    # 上游成功后返回的账号（邮箱）。
    account: Mapped[str] = mapped_column(String(255), default="")
    completed_at: Mapped[str] = mapped_column(String(40), default="")
    # 充值完调用 /check 的到账确认快照（use_status/account/completed_at 等）。
    subscription_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    # 因库存不足在本条上累计的重刷次数。
    stock_retries: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
