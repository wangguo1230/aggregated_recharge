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
