"""AskWhy 服务对前端的请求体模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class VerifyCardRequest(BaseModel):
    card_code: str = Field(..., alias="cardCode", min_length=1)

    model_config = {"populate_by_name": True}


class VerifyTokenRequest(BaseModel):
    # fetchToken 实际是整段 Session JSON 字符串。
    fetch_token: str = Field(..., alias="fetchToken", min_length=1)

    model_config = {"populate_by_name": True}


class CardStatusRequest(BaseModel):
    card_codes: list[str] = Field(..., alias="cardCodes", max_length=200)

    model_config = {"populate_by_name": True}


class CreateOrderRequest(BaseModel):
    card_code: str = Field(..., alias="cardCode", min_length=1)
    fetch_token: str = Field(..., alias="fetchToken", min_length=1)

    model_config = {"populate_by_name": True}


class SubscriptionRequest(BaseModel):
    order_id: str = Field(..., alias="orderId", min_length=1)
    # 可选：不传则后端用该订单加密存储的 fetchToken 查询（独立查订阅 tab 用）。
    fetch_token: str = Field("", alias="fetchToken")

    model_config = {"populate_by_name": True}


class ImportMappingsRequest(BaseModel):
    # 真实 AskWhy 卡密列表，系统为每个生成一个外部码。
    real_cards: list[str] = Field(..., alias="realCards", max_length=500)
    note: str = Field("", max_length=255)

    model_config = {"populate_by_name": True}


class MappingStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(active|disabled)$")


class BatchMappingRequest(BaseModel):
    # 批量操作：启用/停用/删除一组映射（接码卡密、Claude 卡密通用）。
    ids: list[int] = Field(..., max_length=1000)
    action: str = Field(..., pattern="^(enable|disable|delete)$")


class LookupMappingsRequest(BaseModel):
    # 批量外部码/兑换码，反查其对应的原始卡密（卡密映射与接码卡密通用）。
    external_codes: list[str] = Field(..., alias="externalCodes", max_length=500)

    model_config = {"populate_by_name": True}


# ---- 接码（短信）相关请求体 ----
class SmsVerifyRequest(BaseModel):
    # 接码兑换码（外部码），校验后返回手机号。
    card_code: str = Field(..., alias="cardCode", min_length=1)

    model_config = {"populate_by_name": True}


class SmsFetchRequest(BaseModel):
    # 接码兑换码（外部码），后端解析真实卡取查询 URL 拉取短信。
    card_code: str = Field(..., alias="cardCode", min_length=1)

    model_config = {"populate_by_name": True}


class SmsImportMappingsRequest(BaseModel):
    # 真实接码卡密列表，每条形如 手机号----查询URL；系统为每条生成兑换码。
    real_cards: list[str] = Field(..., alias="realCards", max_length=500)
    note: str = Field("", max_length=255)

    model_config = {"populate_by_name": True}


# ---- GPT 充值相关请求体（直调 Gift，无外部码映射）----
class GptCheckRequest(BaseModel):
    # 真实 redeemgpt.com cdkey（客户直接输入，不走外部码映射）。
    cdkey: str = Field(..., min_length=1, max_length=120)


class GptActivateRequest(BaseModel):
    # 真实 cdkey + 账号 Session JSON（session_info），可选 force 跳过套餐检查。
    cdkey: str = Field(..., min_length=1, max_length=120)
    session_info: str = Field(..., alias="sessionInfo", min_length=1)
    force: bool = Field(False)

    model_config = {"populate_by_name": True}


class VipVerifyRequest(BaseModel):
    # 74 渠道验卡：cdk + 账号 JSON。
    cdk: str = Field(..., min_length=1, max_length=120)
    account: str = Field(..., min_length=1)


class VipActivateRequest(BaseModel):
    # 74 渠道充值：cdk + 账号 JSON。
    cdk: str = Field(..., min_length=1, max_length=120)
    account: str = Field(..., min_length=1)


class GptBatchItemInput(BaseModel):
    # 一条批量订阅输入：cdkey + 账号 Session JSON（1:1 配对）。
    cdkey: str = Field(..., min_length=1, max_length=120)
    session_info: str = Field(..., alias="sessionInfo", min_length=1)

    model_config = {"populate_by_name": True}


class GptBatchCreateRequest(BaseModel):
    # 批量订阅任务：一次最多 500 条，后台执行。
    items: list[GptBatchItemInput] = Field(..., min_length=1, max_length=500)
    # 渠道：gpt86（86GPT）/ vip74（74 渠道）；省略默认 gpt86。
    channel: str = Field("gpt86", max_length=20)
    force: bool = Field(False)
    note: str = Field("", max_length=255)
    # 批内并发数；0/省略表示用服务端默认值。上限由服务端 clamp。
    concurrency: int = Field(0, ge=0, le=50)

    model_config = {"populate_by_name": True}
