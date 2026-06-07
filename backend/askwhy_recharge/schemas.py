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
