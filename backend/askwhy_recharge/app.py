"""AskWhy 充值服务 FastAPI 应用。

公开接口（/api/askwhy/*）面向客户：客户提交的是「外部码」，后端经映射表解析成
真实 AskWhy 卡密再转发，响应里剥离真实卡，客户看不到真实卡密与套餐前缀。
管理接口（/api/askwhy/admin/*）需口令鉴权：录入真实卡并自动生成外部码、管理映射。

充值流程：校验卡密(外部码) → 校验 Session JSON → 充值 → 查进度 → 查订阅。
真实卡密与 Session JSON 在创建订单时加密落库（PostgreSQL）。
"""

from __future__ import annotations

import csv
import hmac
import io
import logging
from datetime import datetime

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

from .batch_worker import (
    _CONCURRENCY_CAP,
    account_busy_elsewhere,
    cdkey_already_used,
    configure_worker,
    enqueue_batch,
    start_worker,
)
from .channels import CHANNELS, configure_channels, parse_email, validate_account
from .client import AskWhyApiError, AskWhyClient
from .codes import generate_external_code, normalize_external_code
from .crypto import AskWhyCryptoError, FernetSecretCipher, fingerprint
from .db import get_db_session, init_askwhy_db
from .gift_client import GiftApiError, GiftClient
from .soft_client import SoftClient
from .vip_client import VipApiError, VipClient
from .models import (
    AskWhyCardMappingModel,
    AskWhyOrderModel,
    GptBatchItemModel,
    GptBatchModel,
    GptOrderModel,
    SmsCardMappingModel,
)
from .schemas import (
    BatchMappingRequest,
    CardStatusRequest,
    CreateOrderRequest,
    GptActivateRequest,
    GptBatchCreateRequest,
    GptCheckRequest,
    ImportMappingsRequest,
    LookupMappingsRequest,
    MappingStatusRequest,
    SmsFetchRequest,
    SmsImportMappingsRequest,
    SmsVerifyRequest,
    SubscriptionRequest,
    VerifyCardRequest,
    VerifyTokenRequest,
    VipActivateRequest,
    VipVerifyRequest,
)
from .settings import AskWhySettings, load_askwhy_settings
from .sms_client import SmsApiError, fetch_sms_text, parse_sms, split_card

logger = logging.getLogger(__name__)


def _client(settings: AskWhySettings) -> AskWhyClient:
    return AskWhyClient(
        base_url=settings.askwhy_base_url,
        api_prefix=settings.askwhy_api_prefix,
        proxy=settings.request_proxy,
        timeout=settings.request_timeout_seconds,
        retry_attempts=settings.request_retry_attempts,
    )


def _gift_client(settings: AskWhySettings) -> GiftClient:
    return GiftClient(
        base_url=settings.gift_base_url,
        api_prefix=settings.gift_api_prefix,
        proxy=settings.request_proxy,
        timeout=settings.request_timeout_seconds,
        retry_attempts=settings.request_retry_attempts,
    )


def _vip_client(settings: AskWhySettings) -> VipClient:
    return VipClient(
        base_url=settings.vip_base_url,
        api_prefix=settings.vip_api_prefix,
        proxy=settings.request_proxy,
        timeout=settings.request_timeout_seconds,
        retry_attempts=settings.request_retry_attempts,
    )


def _soft_client(settings: AskWhySettings) -> SoftClient:
    return SoftClient(
        base_url=settings.soft_base_url,
        api_prefix=settings.soft_api_prefix,
        proxy=settings.request_proxy,
        timeout=settings.request_timeout_seconds,
        retry_attempts=settings.request_retry_attempts,
    )


def _fail(message: str) -> dict:
    return {"ok": False, "message": message}


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:80]
    return (request.client.host if request.client else "")[:80]


def create_app() -> FastAPI:
    settings = load_askwhy_settings()
    init_askwhy_db()

    app = FastAPI(title="AskWhy 充值服务", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allow_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    cipher = FernetSecretCipher(settings.secret_key)
    client = _client(settings)
    gift_client = _gift_client(settings)
    vip_client = _vip_client(settings)
    soft_client = _soft_client(settings)

    # 渠道适配器（86GPT / 74 / 软件订阅）+ 批量后台执行器：注入依赖并启动（幂等），同时恢复未完成的批次。
    configure_channels(gift_client, vip_client, soft_client, settings)
    configure_worker(cipher, settings)
    start_worker()

    # ---- 鉴权 ----
    def require_admin(authorization: str = Header("")) -> None:
        if not settings.admin_token:
            raise HTTPException(status_code=503, detail="未配置 ASKWHY_ADMIN_TOKEN，管理接口不可用")
        provided = authorization[7:].strip() if authorization.lower().startswith("bearer ") else authorization.strip()
        if not provided or not hmac.compare_digest(provided, settings.admin_token):
            raise HTTPException(status_code=401, detail="管理员口令无效")

    # ---- 外部码解析 ----
    def resolve_mapping(session: Session, external_input: str) -> AskWhyCardMappingModel | None:
        norm = normalize_external_code(external_input)
        if not norm:
            return None
        return (
            session.query(AskWhyCardMappingModel)
            .filter(
                AskWhyCardMappingModel.external_code_norm == norm,
                AskWhyCardMappingModel.status == "active",
            )
            .first()
        )

    def real_card_of(mapping: AskWhyCardMappingModel) -> str:
        return cipher.decrypt(mapping.real_card_encrypted)

    # ==================== 健康 / 渠道 ====================
    @app.get("/api/askwhy/health")
    def health() -> dict:
        return {"ok": True, "service": "askwhy", "base_url": settings.askwhy_base_url}

    @app.get("/api/askwhy/recharge/channels")
    def recharge_channels() -> dict:
        try:
            return client.channels()
        except AskWhyApiError as exc:
            return _fail(str(exc))

    # ==================== 公开接口（外部码）====================
    @app.post("/api/askwhy/card/verify")
    def verify_card(payload: VerifyCardRequest, session: Session = Depends(get_db_session)) -> dict:
        mapping = resolve_mapping(session, payload.card_code)
        if mapping is None:
            return _fail("卡密不存在或不可用")
        try:
            result = client.verify_card(real_card_of(mapping))
        except (AskWhyApiError, AskWhyCryptoError) as exc:
            return _fail(str(exc))
        if not result.get("ok"):
            return _fail(str(result.get("message") or "卡密不可用"))
        # 白名单重建响应：只回前端需要的字段，code 用外部码，绝不透传上游原始对象。
        card = result.get("card") or {}
        return {
            "ok": True,
            "message": str(result.get("message") or ""),
            "card": {
                "code": mapping.external_code,
                "type": str(card.get("type") or ""),
                "typeLabel": str(card.get("typeLabel") or ""),
                "channelOpen": bool(card.get("channelOpen", False)),
                "canSubmit": bool(card.get("canSubmit", False)),
                "status": str(card.get("status") or ""),
            },
        }

    @app.post("/api/askwhy/token/verify")
    def verify_token(payload: VerifyTokenRequest) -> dict:
        try:
            return client.verify_token(payload.fetch_token.strip())
        except AskWhyApiError as exc:
            return _fail(str(exc))

    @app.post("/api/askwhy/card/status")
    def card_status(payload: CardStatusRequest, session: Session = Depends(get_db_session)) -> dict:
        inputs = [c.strip() for c in payload.card_codes if c.strip()]
        real_to_external: dict[str, str] = {}
        unresolved: list[str] = []
        for raw in inputs:
            mapping = resolve_mapping(session, raw)
            if mapping is None:
                unresolved.append(raw)
                continue
            try:
                real_to_external[real_card_of(mapping)] = mapping.external_code
            except AskWhyCryptoError:
                unresolved.append(raw)

        items: list[dict] = []
        if real_to_external:
            try:
                result = client.cards_batch_query(list(real_to_external.keys()))
            except AskWhyApiError as exc:
                return _fail(str(exc))
            for item in result.get("items") or []:
                real = str(item.get("cardCode") or "")
                external = real_to_external.get(real)
                if external is None:
                    # 万一第三方回显与提交不完全一致：不回退到真实卡，避免泄露。
                    continue
                # 回填外部码，剥离真实卡与置换关系中的真实卡。
                item["cardCode"] = external
                item["previousCardCode"] = ""
                item["replacedByCardCode"] = ""
                items.append(item)
        for raw in unresolved:
            items.append(
                {
                    "cardCode": raw,
                    "cardStatus": "NOT_FOUND",
                    "previousCardCode": "",
                    "replacedByCardCode": "",
                    "rechargeAccount": "",
                    "rechargeTime": None,
                }
            )
        return {"ok": True, "count": len(items), "items": items}

    @app.post("/api/askwhy/exchange/create")
    def create_order(
        payload: CreateOrderRequest,
        request: Request,
        session: Session = Depends(get_db_session),
    ) -> dict:
        fetch_token = payload.fetch_token.strip()
        mapping = resolve_mapping(session, payload.card_code)
        if mapping is None:
            return _fail("卡密不存在或不可用")
        try:
            real_card = real_card_of(mapping)
        except AskWhyCryptoError as exc:
            return _fail(str(exc))

        # 提交前先校验真实卡，拿到充值类型用于落库展示。
        try:
            verify = client.verify_card(real_card)
        except AskWhyApiError as exc:
            return _fail(str(exc))
        if not verify.get("ok"):
            return _fail(str(verify.get("message") or "卡密不可用"))
        card_info = verify.get("card") or {}

        try:
            result = client.create_exchange(real_card, fetch_token)
        except AskWhyApiError as exc:
            return _fail(str(exc))
        if not result.get("ok"):
            return _fail(str(result.get("message") or "订单创建失败"))

        order_id = str(result.get("orderId") or "").strip()
        if not order_id:
            return _fail("AskWhy 未返回订单号")

        # 加密落库：真实卡密 + Session JSON（fetchToken）均不落明文。
        order = AskWhyOrderModel(
            askwhy_order_id=order_id,
            card_code_encrypted=cipher.encrypt(real_card),
            card_fingerprint=fingerprint(real_card, settings.secret_key),
            card_last4=real_card[-4:],
            fetch_token_encrypted=cipher.encrypt(fetch_token),
            external_code=mapping.external_code,
            card_type=str(card_info.get("type") or ""),
            card_type_label=str(card_info.get("typeLabel") or ""),
            status=str(result.get("status") or "PENDING"),
            request_type=str(card_info.get("type") or ""),
            submit_ip=_client_ip(request),
        )
        session.add(order)
        session.commit()

        return {
            "ok": True,
            "message": str(result.get("message") or "订单已创建"),
            "orderId": order_id,
            "status": order.status,
        }

    @app.get("/api/askwhy/exchange/status")
    def order_status(
        orderId: str = Query(..., min_length=1),  # noqa: N803 - 对齐 AskWhy 文档参数名
        session: Session = Depends(get_db_session),
    ) -> dict:
        try:
            result = client.exchange_status(orderId.strip())
        except AskWhyApiError as exc:
            return _fail(str(exc))
        if not result.get("ok"):
            return _fail(str(result.get("message") or "订单不存在"))
        raw = result.get("order") or {}
        _sync_order(session, raw)
        # 白名单重建：只回前端需要的订单字段，绝不透传上游原始对象。
        return {
            "ok": True,
            "order": {
                "id": str(raw.get("id") or ""),
                "status": str(raw.get("status") or ""),
                "email": str(raw.get("email") or ""),
                "requestType": str(raw.get("requestType") or ""),
                "resultMessage": raw.get("resultMessage"),
                "createdAt": raw.get("createdAt"),
                "startedAt": raw.get("startedAt"),
                "completedAt": raw.get("completedAt"),
            },
        }

    @app.post("/api/askwhy/exchange/subscription")
    def order_subscription(
        payload: SubscriptionRequest,
        session: Session = Depends(get_db_session),
    ) -> dict:
        order_id = payload.order_id.strip()
        order = (
            session.query(AskWhyOrderModel)
            .filter(AskWhyOrderModel.askwhy_order_id == order_id)
            .first()
        )
        # fetchToken 优先用入参；缺省则解密该订单存储的 Session JSON。
        fetch_token = payload.fetch_token.strip()
        if not fetch_token:
            if order is None:
                return _fail("订单不存在，且未提供 fetchToken")
            try:
                fetch_token = cipher.decrypt(order.fetch_token_encrypted)
            except AskWhyCryptoError:
                return _fail("无法解密该订单的 Session JSON，请重新提交查询")
        if not fetch_token:
            return _fail("缺少 Session JSON（fetchToken）")

        try:
            result = client.exchange_subscription(order_id, fetch_token)
        except AskWhyApiError as exc:
            return _fail(str(exc))
        if result.get("ok") and isinstance(result.get("subscription"), dict) and order is not None:
            order.subscription_json = dict(result["subscription"])
            session.commit()
        return result

    # ==================== 管理接口（口令鉴权）====================
    @app.post("/api/askwhy/admin/session", dependencies=[Depends(require_admin)])
    def admin_session() -> dict:
        return {"ok": True}

    @app.post("/api/askwhy/admin/mappings/import", dependencies=[Depends(require_admin)])
    def import_mappings(payload: ImportMappingsRequest, session: Session = Depends(get_db_session)) -> dict:
        note = payload.note.strip()[:255]
        seen_in_batch: set[str] = set()
        results: list[dict] = []
        for raw in payload.real_cards:
            real = str(raw or "").strip()
            if not real:
                continue
            fp = fingerprint(real, settings.secret_key)
            if fp in seen_in_batch:
                results.append({"realCard": real, "status": "duplicate", "message": "本次提交内重复"})
                continue
            seen_in_batch.add(fp)

            existing = (
                session.query(AskWhyCardMappingModel)
                .filter(AskWhyCardMappingModel.real_card_fingerprint == fp)
                .first()
            )
            if existing is not None:
                results.append(
                    {
                        "realCard": real,
                        "externalCode": existing.external_code,
                        "typeLabel": existing.card_type_label,
                        "status": "exists",
                        "message": "该真实卡已存在映射",
                    }
                )
                continue

            # 校验真实卡（只读），拿套餐类型；失败不阻断录入。
            card_type = card_type_label = ""
            verify_message = ""
            verify_ok = False
            try:
                verify = client.verify_card(real)
                verify_ok = bool(verify.get("ok"))
                verify_message = str(verify.get("message") or "")
                info = verify.get("card") or {}
                card_type = str(info.get("type") or "")
                card_type_label = str(info.get("typeLabel") or "")
            except AskWhyApiError as exc:
                verify_message = str(exc)

            display, norm = _unique_external_code(session, AskWhyCardMappingModel, "AW")
            mapping = AskWhyCardMappingModel(
                external_code=display,
                external_code_norm=norm,
                real_card_encrypted=cipher.encrypt(real),
                real_card_fingerprint=fp,
                real_card_last4=real[-4:],
                card_type=card_type,
                card_type_label=card_type_label,
                status="active",
                note=note,
            )
            session.add(mapping)
            session.commit()
            results.append(
                {
                    "realCard": real,
                    "externalCode": display,
                    "typeLabel": card_type_label,
                    "status": "created",
                    "message": verify_message if not verify_ok else "已生成",
                    "verifyOk": verify_ok,
                }
            )
        created = sum(1 for r in results if r["status"] == "created")
        return {"ok": True, "created": created, "total": len(results), "results": results}

    @app.get("/api/askwhy/admin/mappings", dependencies=[Depends(require_admin)])
    def list_mappings(
        q: str = Query("", max_length=64),
        limit: int = Query(500, ge=1, le=2000),
        session: Session = Depends(get_db_session),
    ) -> dict:
        query = session.query(AskWhyCardMappingModel)
        keyword = q.strip()
        if keyword:
            norm = normalize_external_code(keyword)
            query = query.filter(AskWhyCardMappingModel.external_code_norm.like(f"%{norm}%"))
        rows = query.order_by(AskWhyCardMappingModel.id.desc()).limit(limit).all()
        items = []
        for row in rows:
            try:
                real_card = cipher.decrypt(row.real_card_encrypted)
            except AskWhyCryptoError:
                real_card = ""
            items.append(
                {
                    "id": row.id,
                    "externalCode": row.external_code,
                    "realCard": real_card,
                    "cardType": row.card_type,
                    "cardTypeLabel": row.card_type_label,
                    "status": row.status,
                    "note": row.note,
                    "createdAt": row.created_at.isoformat() if row.created_at else "",
                }
            )
        return {"ok": True, "count": len(items), "items": items}

    @app.post("/api/askwhy/admin/mappings/lookup", dependencies=[Depends(require_admin)])
    def lookup_mappings(payload: LookupMappingsRequest, session: Session = Depends(get_db_session)) -> dict:
        """批量外部码反查原始卡密：保留输入顺序，按规范化外部码精确匹配，去重。"""

        results: list[dict] = []
        seen: set[str] = set()
        for raw in payload.external_codes:
            code = str(raw or "").strip()
            if not code:
                continue
            norm = normalize_external_code(code)
            if norm in seen:
                continue
            seen.add(norm)
            row = (
                session.query(AskWhyCardMappingModel)
                .filter(AskWhyCardMappingModel.external_code_norm == norm)
                .first()
            )
            if row is None:
                results.append({"input": code, "found": False, "externalCode": "", "realCard": ""})
                continue
            try:
                real_card = cipher.decrypt(row.real_card_encrypted)
            except AskWhyCryptoError:
                real_card = ""
            results.append(
                {
                    "input": code,
                    "found": True,
                    "externalCode": row.external_code,
                    "realCard": real_card,
                    "cardTypeLabel": row.card_type_label,
                    "status": row.status,
                }
            )
        found = sum(1 for r in results if r["found"])
        return {"ok": True, "found": found, "total": len(results), "results": results}

    @app.patch("/api/askwhy/admin/mappings/{mapping_id}", dependencies=[Depends(require_admin)])
    def update_mapping(
        payload: MappingStatusRequest,
        mapping_id: int = Path(..., ge=1),
        session: Session = Depends(get_db_session),
    ) -> dict:
        row = session.get(AskWhyCardMappingModel, mapping_id)
        if row is None:
            return _fail("映射不存在")
        # 已重发的旧外部码为失效终态，不允许再改状态（防止被复活）。
        if row.status == "reissued":
            return _fail("该外部码已重发并失效，不可再变更状态")
        row.status = payload.status
        session.commit()
        return {"ok": True}

    @app.post("/api/askwhy/admin/mappings/{mapping_id}/reissue", dependencies=[Depends(require_admin)])
    def reissue_mapping(
        mapping_id: int = Path(..., ge=1),
        session: Session = Depends(get_db_session),
    ) -> dict:
        """重新生成外部码：旧码置为 reissued 失效，新建一条指向同一真实卡密的 active 记录。

        真实卡密、指纹、套餐信息原样复制：客户拿到的新码可用、旧码自动失效
        （resolve 仅认 active），适用于旧码泄露 / 需重发的换码场景。
        """
        old = session.get(AskWhyCardMappingModel, mapping_id)
        if old is None:
            return _fail("映射不存在")
        if old.status == "reissued":
            return _fail("该外部码已重发，请对最新的外部码操作")
        display, norm = _unique_external_code(session, AskWhyCardMappingModel, "AW")
        fresh = AskWhyCardMappingModel(
            external_code=display,
            external_code_norm=norm,
            real_card_encrypted=old.real_card_encrypted,
            real_card_fingerprint=old.real_card_fingerprint,
            real_card_last4=old.real_card_last4,
            card_type=old.card_type,
            card_type_label=old.card_type_label,
            status="active",
            note=old.note,
        )
        old.status = "reissued"
        session.add(fresh)
        session.commit()
        return {"ok": True, "externalCode": display}

    @app.delete("/api/askwhy/admin/mappings/{mapping_id}", dependencies=[Depends(require_admin)])
    def delete_mapping(
        mapping_id: int = Path(..., ge=1),
        session: Session = Depends(get_db_session),
    ) -> dict:
        row = session.get(AskWhyCardMappingModel, mapping_id)
        if row is None:
            return _fail("映射不存在")
        session.delete(row)
        session.commit()
        return {"ok": True}

    @app.get("/api/askwhy/admin/orders", dependencies=[Depends(require_admin)])
    def list_orders(
        q: str = Query("", max_length=120),
        limit: int = Query(200, ge=1, le=1000),
        session: Session = Depends(get_db_session),
    ) -> dict:
        query = session.query(AskWhyOrderModel)
        keyword = q.strip()
        if keyword:
            like = f"%{keyword}%"
            query = query.filter(
                (AskWhyOrderModel.askwhy_order_id.like(like))
                | (AskWhyOrderModel.external_code.like(like))
                | (AskWhyOrderModel.account_email.like(like))
            )
        rows = query.order_by(AskWhyOrderModel.id.desc()).limit(limit).all()
        items = []
        for row in rows:
            try:
                real_card = cipher.decrypt(row.card_code_encrypted) if row.card_code_encrypted else ""
            except AskWhyCryptoError:
                real_card = ""
            sub = row.subscription_json or {}
            items.append(
                {
                    "id": row.id,
                    "orderId": row.askwhy_order_id,
                    "externalCode": row.external_code,
                    "realCard": real_card,
                    "cardTypeLabel": row.card_type_label,
                    "status": row.status,
                    "accountEmail": row.account_email,
                    "resultMessage": row.result_message,
                    "submitIp": row.submit_ip,
                    "subscriptionUntil": sub.get("activeUntilBeijing") or sub.get("activeUntil") or "",
                    "createdAt": row.created_at.isoformat() if row.created_at else "",
                    "updatedAt": row.updated_at.isoformat() if row.updated_at else "",
                }
            )
        return {"ok": True, "count": len(items), "items": items}

    # ==================== 接码（短信）====================
    def resolve_sms_mapping(session: Session, external_input: str) -> SmsCardMappingModel | None:
        norm = normalize_external_code(external_input)
        if not norm:
            return None
        return (
            session.query(SmsCardMappingModel)
            .filter(
                SmsCardMappingModel.external_code_norm == norm,
                SmsCardMappingModel.status == "active",
            )
            .first()
        )

    @app.post("/api/sms/card/verify")
    def sms_verify(payload: SmsVerifyRequest, session: Session = Depends(get_db_session)) -> dict:
        mapping = resolve_sms_mapping(session, payload.card_code)
        if mapping is None:
            return _fail("兑换码不存在或不可用")
        # 只回兑换码与手机号，绝不暴露查询 URL。
        return {
            "ok": True,
            "card": {"code": mapping.external_code, "phone": mapping.phone},
        }

    @app.post("/api/sms/fetch")
    def sms_fetch(payload: SmsFetchRequest, session: Session = Depends(get_db_session)) -> dict:
        mapping = resolve_sms_mapping(session, payload.card_code)
        if mapping is None:
            return _fail("兑换码不存在或不可用")
        try:
            real_card = cipher.decrypt(mapping.real_card_encrypted)
        except AskWhyCryptoError as exc:
            return _fail(str(exc))
        _, url = split_card(real_card)
        if not url:
            return _fail("接码卡密格式异常（缺少查询地址）")
        try:
            text = fetch_sms_text(
                url,
                proxy=settings.request_proxy,
                timeout=settings.request_timeout_seconds,
                retry_attempts=settings.request_retry_attempts,
            )
        except SmsApiError as exc:
            return _fail(str(exc))
        parsed = parse_sms(text)
        return {
            "ok": True,
            "phone": mapping.phone,
            "hasSms": parsed["hasSms"],
            "code": parsed["code"],
            "content": parsed["content"],
        }

    # ---- 接码卡密管理（复用同一管理口令）----
    @app.post("/api/sms/admin/mappings/import", dependencies=[Depends(require_admin)])
    def sms_import_mappings(
        payload: SmsImportMappingsRequest, session: Session = Depends(get_db_session)
    ) -> dict:
        note = payload.note.strip()[:255]
        seen_in_batch: set[str] = set()
        results: list[dict] = []
        for raw in payload.real_cards:
            real = str(raw or "").strip()
            if not real:
                continue
            phone, url = split_card(real)
            if not phone or not url:
                results.append({"phone": phone, "status": "invalid", "message": "格式应为 手机号----查询URL"})
                continue

            fp = fingerprint(real, settings.secret_key)
            if fp in seen_in_batch:
                results.append({"phone": phone, "status": "duplicate", "message": "本次提交内重复"})
                continue
            seen_in_batch.add(fp)

            existing = (
                session.query(SmsCardMappingModel)
                .filter(SmsCardMappingModel.real_card_fingerprint == fp)
                .first()
            )
            if existing is not None:
                results.append(
                    {
                        "phone": phone,
                        "externalCode": existing.external_code,
                        "status": "exists",
                        "message": "该接码卡密已存在映射",
                    }
                )
                continue

            display, norm = _unique_external_code(session, SmsCardMappingModel, "SM")
            mapping = SmsCardMappingModel(
                external_code=display,
                external_code_norm=norm,
                real_card_encrypted=cipher.encrypt(real),
                real_card_fingerprint=fp,
                phone=phone,
                status="active",
                note=note,
            )
            session.add(mapping)
            session.commit()
            results.append(
                {"phone": phone, "externalCode": display, "status": "created", "message": "已生成"}
            )
        created = sum(1 for r in results if r["status"] == "created")
        return {"ok": True, "created": created, "total": len(results), "results": results}

    @app.get("/api/sms/admin/mappings", dependencies=[Depends(require_admin)])
    def sms_list_mappings(
        q: str = Query("", max_length=64),
        limit: int = Query(500, ge=1, le=2000),
        session: Session = Depends(get_db_session),
    ) -> dict:
        query = session.query(SmsCardMappingModel)
        keyword = q.strip()
        if keyword:
            norm = normalize_external_code(keyword)
            like = f"%{keyword}%"
            query = query.filter(
                (SmsCardMappingModel.external_code_norm.like(f"%{norm}%"))
                | (SmsCardMappingModel.phone.like(like))
            )
        rows = query.order_by(SmsCardMappingModel.id.desc()).limit(limit).all()
        items = []
        for row in rows:
            try:
                real_card = cipher.decrypt(row.real_card_encrypted)
            except AskWhyCryptoError:
                real_card = ""
            items.append(
                {
                    "id": row.id,
                    "externalCode": row.external_code,
                    "phone": row.phone,
                    "realCard": real_card,
                    "status": row.status,
                    "note": row.note,
                    "createdAt": row.created_at.isoformat() if row.created_at else "",
                }
            )
        return {"ok": True, "count": len(items), "items": items}

    @app.post("/api/sms/admin/mappings/lookup", dependencies=[Depends(require_admin)])
    def sms_lookup_mappings(payload: LookupMappingsRequest, session: Session = Depends(get_db_session)) -> dict:
        """批量兑换码反查接码原始卡密（手机号----URL）：保留输入顺序，精确匹配，去重。"""

        results: list[dict] = []
        seen: set[str] = set()
        for raw in payload.external_codes:
            code = str(raw or "").strip()
            if not code:
                continue
            norm = normalize_external_code(code)
            if norm in seen:
                continue
            seen.add(norm)
            row = (
                session.query(SmsCardMappingModel)
                .filter(SmsCardMappingModel.external_code_norm == norm)
                .first()
            )
            if row is None:
                results.append({"input": code, "found": False, "externalCode": "", "realCard": "", "phone": ""})
                continue
            try:
                real_card = cipher.decrypt(row.real_card_encrypted)
            except AskWhyCryptoError:
                real_card = ""
            results.append(
                {
                    "input": code,
                    "found": True,
                    "externalCode": row.external_code,
                    "realCard": real_card,
                    "phone": row.phone,
                    "status": row.status,
                }
            )
        found = sum(1 for r in results if r["found"])
        return {"ok": True, "found": found, "total": len(results), "results": results}

    @app.patch("/api/sms/admin/mappings/{mapping_id}", dependencies=[Depends(require_admin)])
    def sms_update_mapping(
        payload: MappingStatusRequest,
        mapping_id: int = Path(..., ge=1),
        session: Session = Depends(get_db_session),
    ) -> dict:
        row = session.get(SmsCardMappingModel, mapping_id)
        if row is None:
            return _fail("映射不存在")
        # 已重发的旧兑换码为失效终态，不允许再改状态（防止被复活）。
        if row.status == "reissued":
            return _fail("该兑换码已重发并失效，不可再变更状态")
        row.status = payload.status
        session.commit()
        return {"ok": True}

    @app.post("/api/sms/admin/mappings/{mapping_id}/reissue", dependencies=[Depends(require_admin)])
    def sms_reissue_mapping(
        mapping_id: int = Path(..., ge=1),
        session: Session = Depends(get_db_session),
    ) -> dict:
        """重新生成兑换码：旧码置为 reissued 失效，新建一条指向同一接码卡密的 active 记录。"""
        old = session.get(SmsCardMappingModel, mapping_id)
        if old is None:
            return _fail("映射不存在")
        if old.status == "reissued":
            return _fail("该兑换码已重发，请对最新的兑换码操作")
        display, norm = _unique_external_code(session, SmsCardMappingModel, "SM")
        fresh = SmsCardMappingModel(
            external_code=display,
            external_code_norm=norm,
            real_card_encrypted=old.real_card_encrypted,
            real_card_fingerprint=old.real_card_fingerprint,
            phone=old.phone,
            status="active",
            note=old.note,
        )
        old.status = "reissued"
        session.add(fresh)
        session.commit()
        return {"ok": True, "externalCode": display}

    @app.delete("/api/sms/admin/mappings/{mapping_id}", dependencies=[Depends(require_admin)])
    def sms_delete_mapping(
        mapping_id: int = Path(..., ge=1),
        session: Session = Depends(get_db_session),
    ) -> dict:
        row = session.get(SmsCardMappingModel, mapping_id)
        if row is None:
            return _fail("映射不存在")
        session.delete(row)
        session.commit()
        return {"ok": True}

    @app.post("/api/sms/admin/mappings/batch", dependencies=[Depends(require_admin)])
    def sms_batch_mappings(
        payload: BatchMappingRequest,
        session: Session = Depends(get_db_session),
    ) -> dict:
        """批量启用/停用/删除接码卡密映射。"""
        affected = _batch_mapping_op(session, SmsCardMappingModel, payload.ids, payload.action)
        return {"ok": True, "affected": affected}

    # ==================== GPT 充值（Gift 上游，直调无映射）====================
    @app.post("/api/gpt/card/verify")
    def gpt_verify(payload: GptCheckRequest) -> dict:
        """直查真实 cdkey：调上游 check，校验产品类型为 gpt，回包不含外部码（客户已持有真实卡）。"""
        cdkey = payload.cdkey.strip()
        try:
            result = gift_client.check(cdkey)
        except GiftApiError as exc:
            return _fail(str(exc))
        if not result.get("success"):
            return _fail(str(result.get("msg") or "卡密不可用"))
        data = result.get("data") if isinstance(result.get("data"), dict) else {}
        app_name = str(data.get("app") or "")
        # 仅接受 GPT 卡密：非 gpt 产品避免提交字段不匹配。
        if app_name and app_name != "gpt":
            return _fail("该卡密不是 GPT 充值卡密，请到对应充值页提交")
        return {
            "ok": True,
            "message": str(result.get("msg") or ""),
            "card": {
                "giftName": str(data.get("gift_name") or ""),
                "app": app_name or "gpt",
                "useStatus": data.get("use_status"),
                "statusHint": str(data.get("status_hint") or ""),
                "account": str(data.get("account") or ""),
                "completedAt": str(data.get("completed_at") or ""),
                "inCooldown": bool(data.get("in_cooldown", False)),
                "cooldownRemaining": data.get("cooldown_remaining") or 0,
            },
        }

    @app.post("/api/gpt/activate")
    def gpt_activate(
        payload: GptActivateRequest,
        request: Request,
        session: Session = Depends(get_db_session),
    ) -> dict:
        """真实 cdkey + Session JSON 直接提交上游 activate，落库订单（cdkey 与 Session 均加密）。"""
        cdkey = payload.cdkey.strip()
        session_info = payload.session_info.strip()
        try:
            result = gift_client.activate_session(cdkey, session_info, force=payload.force)
        except GiftApiError as exc:
            return _fail(str(exc))

        success = bool(result.get("success"))
        data = result.get("data") if isinstance(result.get("data"), dict) else {}
        use_status = data.get("use_status")
        if success and use_status == 1:
            status = "SUCCEEDED"
        elif use_status == -1:
            status = "PROCESSING"
        elif not success:
            status = "FAILED"
        else:
            status = "PENDING"

        # 按真实卡指纹 upsert（限本渠道），避免同一卡密重复提交产生多行。
        fp = fingerprint(cdkey, settings.secret_key)
        order = (
            session.query(GptOrderModel)
            .filter(GptOrderModel.card_fingerprint == fp, GptOrderModel.channel == "gpt86")
            .order_by(GptOrderModel.id.desc())
            .first()
        )
        if order is None:
            order = GptOrderModel(
                channel="gpt86",
                card_code_encrypted=cipher.encrypt(cdkey),
                card_fingerprint=fp,
                card_last4=cdkey[-4:],
            )
            session.add(order)
        order.session_info_encrypted = cipher.encrypt(session_info)
        order.gift_name = str(data.get("gift_name") or "")
        order.use_status = int(use_status) if isinstance(use_status, (int, float)) else order.use_status
        order.status = status
        order.result_message = str(result.get("msg") or "")
        order.account = str(data.get("account") or "")
        order.completed_at = str(data.get("completed_at") or "")
        order.submit_ip = _client_ip(request)
        session.commit()

        return {
            "ok": success,
            "message": str(result.get("msg") or ""),
            "order": {
                "giftName": order.gift_name,
                "useStatus": use_status,
                "account": order.account,
                "completedAt": order.completed_at,
            },
        }

    # ---- 74 渠道客户单笔充值（直调 zzlokp12）----
    @app.post("/api/vip/card/verify")
    def vip_card_verify(payload: VipVerifyRequest) -> dict:
        """74 验卡：cdk + 账号 JSON 调上游 /vip/c。"""
        try:
            result = vip_client.verify(payload.cdk.strip(), payload.account.strip())
        except VipApiError as exc:
            return _fail(str(exc))
        if result.get("code") != 1:
            return _fail(str(result.get("message") or "卡密验证未通过"))
        return {"ok": True, "message": str(result.get("message") or "卡密验证通过")}

    @app.post("/api/vip/activate")
    def vip_activate(
        payload: VipActivateRequest,
        request: Request,
        session: Session = Depends(get_db_session),
    ) -> dict:
        """74 充值：cdk + 账号 JSON 调上游 /vip/r，落库订单（channel=vip74，cdk 与账号均加密）。"""
        cdk = payload.cdk.strip()
        account = payload.account.strip()
        try:
            result = vip_client.recharge(cdk, account)
        except VipApiError as exc:
            return _fail(str(exc))

        success = result.get("code") == 1
        message = str(result.get("message") or "")
        status = "SUCCEEDED" if success else "FAILED"

        fp = fingerprint(cdk, settings.secret_key)
        order = (
            session.query(GptOrderModel)
            .filter(GptOrderModel.card_fingerprint == fp, GptOrderModel.channel == "vip74")
            .order_by(GptOrderModel.id.desc())
            .first()
        )
        if order is None:
            order = GptOrderModel(
                channel="vip74",
                card_code_encrypted=cipher.encrypt(cdk),
                card_fingerprint=fp,
                card_last4=cdk[-4:],
            )
            session.add(order)
        order.session_info_encrypted = cipher.encrypt(account)
        order.use_status = 1 if success else 0
        order.status = status
        order.result_message = message
        order.account = parse_email(account)
        order.submit_ip = _client_ip(request)
        session.commit()

        return {
            "ok": success,
            "message": message or ("充值成功" if success else "充值失败"),
            "order": {"account": order.account, "status": status},
        }

    @app.get("/api/gpt/admin/orders", dependencies=[Depends(require_admin)])
    def gpt_list_orders(
        q: str = Query("", max_length=120),
        channel: str = Query("", max_length=20),
        limit: int = Query(200, ge=1, le=1000),
        session: Session = Depends(get_db_session),
    ) -> dict:
        query = session.query(GptOrderModel)
        if channel.strip():
            query = query.filter(GptOrderModel.channel == channel.strip())
        keyword = q.strip()
        if keyword:
            like = f"%{keyword}%"
            query = query.filter(
                (GptOrderModel.card_last4.like(like)) | (GptOrderModel.account.like(like))
            )
        rows = query.order_by(GptOrderModel.id.desc()).limit(limit).all()
        items = []
        for row in rows:
            try:
                real_card = cipher.decrypt(row.card_code_encrypted) if row.card_code_encrypted else ""
            except AskWhyCryptoError:
                real_card = ""
            items.append(
                {
                    "id": row.id,
                    "channel": row.channel,
                    "realCard": real_card,
                    "giftName": row.gift_name,
                    "useStatus": row.use_status,
                    "status": row.status,
                    "resultMessage": row.result_message,
                    "account": row.account,
                    "completedAt": row.completed_at,
                    "submitIp": row.submit_ip,
                    "createdAt": row.created_at.isoformat() if row.created_at else "",
                    "updatedAt": row.updated_at.isoformat() if row.updated_at else "",
                }
            )
        return {"ok": True, "count": len(items), "items": items}

    # ---- GPT 批量订阅（管理员）----
    def _batch_counts(session: Session, batch_ids: list[int]) -> dict[int, dict[str, int]]:
        """按 (batch_id, status) 聚合条目计数；计数不在批次表冗余，避免漂移。"""
        counts: dict[int, dict[str, int]] = {}
        if not batch_ids:
            return counts
        rows = (
            session.query(GptBatchItemModel.batch_id, GptBatchItemModel.status, func.count())
            .filter(GptBatchItemModel.batch_id.in_(batch_ids))
            .group_by(GptBatchItemModel.batch_id, GptBatchItemModel.status)
            .all()
        )
        for batch_id, status, count in rows:
            counts.setdefault(batch_id, {})[status] = int(count)
        return counts

    def _retry_waiting_ids(session: Session, batch_ids: list[int]) -> set[int]:
        """当前有条目在等待重试（SUBMITTING 且已发生过重试 stock_retries>0）的批次集合，渠道无关。"""
        if not batch_ids:
            return set()
        rows = (
            session.query(GptBatchItemModel.batch_id)
            .filter(
                GptBatchItemModel.batch_id.in_(batch_ids),
                GptBatchItemModel.status == "SUBMITTING",
                GptBatchItemModel.stock_retries > 0,
            )
            .distinct()
            .all()
        )
        return {r[0] for r in rows}

    def _batch_summary(batch: GptBatchModel, counts: dict[str, int], retry_waiting: bool) -> dict:
        """批次摘要（含派生的实时执行状态），list / detail 复用。"""
        return {
            "id": batch.id,
            "channel": batch.channel,
            "status": batch.status,
            "force": batch.force,
            "note": batch.note,
            "total": batch.total,
            "concurrency": batch.concurrency,
            "cancelRequested": batch.cancel_requested,
            "inFlight": counts.get("SUBMITTING", 0),  # 当前并发在处理的条数
            "retryWaiting": retry_waiting,  # 是否有条目在等待重试（缺货/冷却/临时异常）
            "pausedReason": batch.paused_reason,
            "counts": counts,
            "createdAt": batch.created_at.isoformat() if batch.created_at else "",
            "startedAt": batch.started_at.isoformat() if batch.started_at else "",
            "finishedAt": batch.finished_at.isoformat() if batch.finished_at else "",
        }

    # 进行中的批次状态（用于「一次只跑一批」并发守卫）。
    _ACTIVE_BATCH_STATUSES = ("PENDING", "RUNNING", "PAUSED")

    @app.post("/api/gpt/admin/batch", dependencies=[Depends(require_admin)])
    def gpt_create_batch(payload: GptBatchCreateRequest, session: Session = Depends(get_db_session)) -> dict:
        """建批：逐条加密落库；批内去重 + 账号校验 + cdkey 复用拦截（按渠道隔离），合格条目入队执行。

        一次只跑一批（按渠道）：该渠道已有进行中（待执行/执行中/已暂停）任务时拒绝新建。
        """
        channel = (payload.channel or "gpt86").strip()
        if channel not in CHANNELS:
            return _fail(f"未知渠道：{channel}")

        active = (
            session.query(GptBatchModel)
            .filter(GptBatchModel.channel == channel, GptBatchModel.status.in_(_ACTIVE_BATCH_STATUSES))
            .order_by(GptBatchModel.id.desc())
            .first()
        )
        if active is not None:
            return _fail(f"该渠道已有进行中的批量任务（#{active.id}，{active.status}），请先完成或取消后再创建")

        # 并发数：0/省略用服务端默认，clamp 到 [1, 上限]。
        concurrency = payload.concurrency or settings.batch_concurrency
        concurrency = max(1, min(_CONCURRENCY_CAP, concurrency))

        batch = GptBatchModel(
            channel=channel,
            status="PENDING",
            force=bool(payload.force),
            note=payload.note.strip()[:255],
            total=len(payload.items),
            concurrency=concurrency,
        )
        session.add(batch)
        session.flush()  # 取得 batch.id

        seen_cdkey: set[str] = set()
        seen_session: set[str] = set()
        results: list[dict] = []
        for index, raw in enumerate(payload.items, start=1):
            cdkey = raw.cdkey.strip()
            account = raw.session_info.strip()
            cdkey_fp = fingerprint(cdkey, settings.secret_key)
            session_fp = fingerprint(account, settings.secret_key)
            email = parse_email(account)

            status, code, message = "PENDING", "", ""
            if cdkey_fp in seen_cdkey:
                status, code, message = "SKIPPED", "batch.duplicate_cdkey", "批内重复卡密"
            elif session_fp in seen_session:
                status, code, message = "SKIPPED", "batch.duplicate_account", "批内重复账号"
            elif not validate_account(channel, account):
                status, code, message = "SKIPPED", "input.account_invalid", "账号 JSON 无法解析或缺少必要字段"
            elif cdkey_already_used(session, cdkey_fp, channel, include_pending=True):
                status, code, message = "SKIPPED", "cdk.already_used", "该卡密已被使用或已在其他批次排队"
            elif account_busy_elsewhere(session, session_fp, channel):
                status, code, message = "SKIPPED", "account.busy_elsewhere", "该账号已在其他批次排队/处理中"
            seen_cdkey.add(cdkey_fp)
            seen_session.add(session_fp)

            session.add(
                GptBatchItemModel(
                    batch_id=batch.id,
                    channel=channel,
                    seq=index,
                    cdkey_encrypted=cipher.encrypt(cdkey),
                    cdkey_fingerprint=cdkey_fp,
                    cdkey_last4=cdkey[-4:],
                    session_info_encrypted=cipher.encrypt(account),
                    session_fingerprint=session_fp,
                    email=email,
                    status=status,
                    result_code=code,
                    result_message=message,
                )
            )
            results.append({"seq": index, "email": email, "cdkeyLast4": cdkey[-4:], "status": status, "message": message})

        accepted = sum(1 for r in results if r["status"] == "PENDING")
        if accepted == 0:
            # 没有可执行条目，直接终态，避免空转入队。
            batch.status = "DONE"
            batch.finished_at = datetime.utcnow()
        session.commit()

        if accepted > 0:
            enqueue_batch(batch.id)

        return {
            "ok": True,
            "batchId": batch.id,
            "total": len(payload.items),
            "accepted": accepted,
            "skipped": len(payload.items) - accepted,
            "results": results,
        }

    @app.get("/api/gpt/admin/batch", dependencies=[Depends(require_admin)])
    def gpt_list_batches(
        channel: str = Query("", max_length=20),
        q: str = Query("", max_length=80),
        status: str = Query("", max_length=20),
        limit: int = Query(100, ge=1, le=500),
        session: Session = Depends(get_db_session),
    ) -> dict:
        query = session.query(GptBatchModel)
        if channel.strip():
            query = query.filter(GptBatchModel.channel == channel.strip())
        if status.strip():
            query = query.filter(GptBatchModel.status == status.strip())
        keyword = q.strip()
        if keyword:
            # 按备注模糊 + 编号精确（便于一批批导入后检索）。
            cond = GptBatchModel.note.ilike(f"%{keyword}%")
            if keyword.isdigit():
                cond = cond | (GptBatchModel.id == int(keyword))
            query = query.filter(cond)
        rows = query.order_by(GptBatchModel.id.desc()).limit(limit).all()
        ids = [r.id for r in rows]
        counts = _batch_counts(session, ids)
        waiting = _retry_waiting_ids(session, ids)
        items = [_batch_summary(r, counts.get(r.id, {}), r.id in waiting) for r in rows]
        return {"ok": True, "count": len(items), "items": items}

    @app.get("/api/gpt/admin/batch/{batch_id}", dependencies=[Depends(require_admin)])
    def gpt_batch_detail(
        batch_id: int = Path(..., ge=1),
        session: Session = Depends(get_db_session),
    ) -> dict:
        batch = session.get(GptBatchModel, batch_id)
        if batch is None:
            return _fail("批量任务不存在")
        rows = (
            session.query(GptBatchItemModel)
            .filter(GptBatchItemModel.batch_id == batch_id)
            .order_by(GptBatchItemModel.seq.asc())
            .all()
        )
        # 明细不回真实 cdkey / Session（敏感），仅回尾号、邮箱与状态结果。
        items = [
            {
                "seq": it.seq,
                "email": it.email,
                "cdkeyLast4": it.cdkey_last4,
                "status": it.status,
                "useStatus": it.use_status,
                "resultCode": it.result_code,
                "resultMessage": it.result_message,
                "account": it.account,
                "completedAt": it.completed_at,
                "attempts": it.attempts,
            }
            for it in rows
        ]
        counts = _batch_counts(session, [batch_id]).get(batch_id, {})
        retry_waiting = batch_id in _retry_waiting_ids(session, [batch_id])
        return {
            "ok": True,
            "batch": _batch_summary(batch, counts, retry_waiting),
            "items": items,
        }

    @app.post("/api/gpt/admin/batch/{batch_id}/cancel", dependencies=[Depends(require_admin)])
    def gpt_cancel_batch(
        batch_id: int = Path(..., ge=1),
        session: Session = Depends(get_db_session),
    ) -> dict:
        batch = session.get(GptBatchModel, batch_id)
        if batch is None:
            return _fail("批量任务不存在")
        if batch.status in ("DONE", "CANCELLED"):
            return _fail("任务已结束，无法取消")
        batch.cancel_requested = True
        if batch.status == "PAUSED":
            # 暂停态没有执行线程在跑，直接就地收尾：剩余 PENDING 标 SKIPPED。
            session.query(GptBatchItemModel).filter(
                GptBatchItemModel.batch_id == batch_id,
                GptBatchItemModel.status == "PENDING",
            ).update(
                {
                    GptBatchItemModel.status: "SKIPPED",
                    GptBatchItemModel.result_code: "batch.cancelled",
                    GptBatchItemModel.result_message: "批量任务已取消",
                },
                synchronize_session=False,
            )
            batch.status = "CANCELLED"
            if batch.finished_at is None:
                batch.finished_at = datetime.utcnow()
        # 其余状态（PENDING/RUNNING）仅置位，由执行线程在下一条之前读取并停止；在途条目正常落库。
        session.commit()
        return {"ok": True}

    @app.post("/api/gpt/admin/batch/{batch_id}/resume", dependencies=[Depends(require_admin)])
    def gpt_resume_batch(
        batch_id: int = Path(..., ge=1),
        concurrency: int = Query(0, ge=0, le=50),
        session: Session = Depends(get_db_session),
    ) -> dict:
        """继续被暂停的批量任务：从剩余 PENDING 条目接着执行（出错的条目已是终态，自动跳过）。

        concurrency>0 时同时更新本批次的并发数（重跑用新并发）。
        """
        batch = session.get(GptBatchModel, batch_id)
        if batch is None:
            return _fail("批量任务不存在")
        if batch.status != "PAUSED":
            return _fail("只有已暂停的任务才能继续")
        if concurrency > 0:
            batch.concurrency = max(1, min(_CONCURRENCY_CAP, concurrency))
        remaining = (
            session.query(GptBatchItemModel.id)
            .filter(GptBatchItemModel.batch_id == batch_id, GptBatchItemModel.status == "PENDING")
            .first()
        )
        if remaining is None:
            # 没有可继续的条目，直接收尾为完成。
            batch.status = "DONE"
            batch.paused_reason = ""
            if batch.finished_at is None:
                batch.finished_at = datetime.utcnow()
            session.commit()
            return {"ok": True, "status": "DONE"}
        batch.status = "PENDING"
        batch.paused_reason = ""
        session.commit()
        enqueue_batch(batch.id)
        return {"ok": True, "status": "PENDING"}

    @app.post("/api/gpt/admin/batch/{batch_id}/items/{seq}/retry", dependencies=[Depends(require_admin)])
    def gpt_retry_item(
        batch_id: int = Path(..., ge=1),
        seq: int = Path(..., ge=1),
        force: bool = Query(False),
        concurrency: int = Query(0, ge=0, le=50),
        session: Session = Depends(get_db_session),
    ) -> dict:
        """重新提交单个失败/跳过的条目：重置为 PENDING 并重新激活本批次执行。

        NEEDS_REVIEW（结果未知）默认拒绝，必须 force=1 显式确认（操作者已核实确未到账）。
        """
        item = (
            session.query(GptBatchItemModel)
            .filter(GptBatchItemModel.batch_id == batch_id, GptBatchItemModel.seq == seq)
            .first()
        )
        if item is None:
            return _fail("条目不存在")
        if item.status in ("PENDING", "SUBMITTING"):
            return _fail("该条目正在排队/处理中")
        if item.status == "SUCCEEDED":
            return _fail("该条目已成功，无需重试")
        if item.status == "NEEDS_REVIEW" and not force:
            return _fail("该条目结果未知（可能已扣卡），请先人工核实；确认未到账后再强制重试")

        batch = session.get(GptBatchModel, batch_id)
        if batch is None:
            return _fail("批量任务不存在")
        if batch.status == "RUNNING":
            return _fail("任务执行中，请等其暂停或结束后再重试单条")

        # 一次只跑一批：除本批外不能有其他进行中的任务。
        other = (
            session.query(GptBatchModel.id)
            .filter(
                GptBatchModel.status.in_(_ACTIVE_BATCH_STATUSES),
                GptBatchModel.id != batch_id,
            )
            .first()
        )
        if other is not None:
            return _fail(f"已有其他进行中的批量任务（#{other[0]}），请先完成或取消")

        # 复检卡密是否已在别处被用过（成功/处理中/提交中/待人工）。
        if cdkey_already_used(session, item.cdkey_fingerprint, item.channel, exclude_item_id=item.id):
            return _fail("该卡密已被其他条目使用，不能重试")

        # 重置条目为待处理。
        item.status = "PENDING"
        item.result_code = ""
        item.result_message = ""
        item.use_status = None
        item.account = ""
        item.completed_at = ""
        item.stock_retries = 0
        item.subscription_json = {}
        # 重新激活批次（终态/暂停 → 待执行），清掉取消/暂停/完成标记。
        if concurrency > 0:
            batch.concurrency = max(1, min(_CONCURRENCY_CAP, concurrency))
        batch.status = "PENDING"
        batch.cancel_requested = False
        batch.paused_reason = ""
        batch.finished_at = None
        session.commit()
        enqueue_batch(batch_id)
        return {"ok": True}

    @app.post("/api/gpt/admin/batch/{batch_id}/retry-failed", dependencies=[Depends(require_admin)])
    def gpt_retry_failed(
        batch_id: int = Path(..., ge=1),
        include_review: bool = Query(False),
        concurrency: int = Query(0, ge=0, le=50),
        session: Session = Depends(get_db_session),
    ) -> dict:
        """一键重试整批的失败/跳过条目：批量重置为 PENDING 并重新激活执行。

        默认重试 FAILED + SKIPPED；include_review=1 时连 NEEDS_REVIEW 一并重试（需操作者已核实）。
        已被别处用过的卡密会跳过，不重置。
        """
        batch = session.get(GptBatchModel, batch_id)
        if batch is None:
            return _fail("批量任务不存在")
        if batch.status == "RUNNING":
            return _fail("任务执行中，请等其暂停或结束后再批量重试")
        other = (
            session.query(GptBatchModel.id)
            .filter(GptBatchModel.status.in_(_ACTIVE_BATCH_STATUSES), GptBatchModel.id != batch_id)
            .first()
        )
        if other is not None:
            return _fail(f"已有其他进行中的批量任务（#{other[0]}），请先完成或取消")

        target_statuses = ["FAILED", "SKIPPED"]
        if include_review:
            target_statuses.append("NEEDS_REVIEW")
        rows = (
            session.query(GptBatchItemModel)
            .filter(
                GptBatchItemModel.batch_id == batch_id,
                GptBatchItemModel.status.in_(target_statuses),
            )
            .all()
        )
        reset = 0
        for item in rows:
            # 复检卡密未被别处占用，避免重复扣。
            if cdkey_already_used(session, item.cdkey_fingerprint, item.channel, exclude_item_id=item.id):
                continue
            item.status = "PENDING"
            item.result_code = ""
            item.result_message = ""
            item.use_status = None
            item.account = ""
            item.completed_at = ""
            item.stock_retries = 0
            item.subscription_json = {}
            reset += 1

        if reset == 0:
            session.rollback()
            return _fail("没有可重试的条目")

        if concurrency > 0:
            batch.concurrency = max(1, min(_CONCURRENCY_CAP, concurrency))
        batch.status = "PENDING"
        batch.cancel_requested = False
        batch.paused_reason = ""
        batch.finished_at = None
        session.commit()
        enqueue_batch(batch_id)
        return {"ok": True, "reset": reset}

    @app.get("/api/gpt/admin/batch/{batch_id}/export", dependencies=[Depends(require_admin)])
    def gpt_export_batch(
        batch_id: int = Path(..., ge=1),
        session: Session = Depends(get_db_session),
    ) -> Response:
        """导出批次结果为 CSV（含真实 cdkey，供交付/对账）。"""
        batch = session.get(GptBatchModel, batch_id)
        if batch is None:
            raise HTTPException(status_code=404, detail="批量任务不存在")
        rows = (
            session.query(GptBatchItemModel)
            .filter(GptBatchItemModel.batch_id == batch_id)
            .order_by(GptBatchItemModel.seq.asc())
            .all()
        )
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        # credential：账号（86 账号行模式下含轮转后的新 rt，供回收/重导）；
        # session_json：实际提交给上游的拼接好的 session_info。
        writer.writerow(
            [
                "seq", "email", "cdkey", "credential", "session_json", "status", "use_status",
                "result_code", "result_message", "account", "completed_at", "attempts",
            ]
        )
        for item in rows:
            try:
                cdkey = cipher.decrypt(item.cdkey_encrypted) if item.cdkey_encrypted else ""
            except AskWhyCryptoError:
                cdkey = ""
            try:
                credential = cipher.decrypt(item.session_info_encrypted) if item.session_info_encrypted else ""
            except AskWhyCryptoError:
                credential = ""
            try:
                session_json = cipher.decrypt(item.built_session_encrypted) if item.built_session_encrypted else ""
            except AskWhyCryptoError:
                session_json = ""
            writer.writerow(
                [
                    item.seq,
                    item.email,
                    cdkey,
                    credential,
                    session_json,
                    item.status,
                    item.use_status if item.use_status is not None else "",
                    item.result_code,
                    item.result_message,
                    item.account,
                    item.completed_at,
                    item.attempts,
                ]
            )
        # 带 BOM，Excel 直接打开中文不乱码。
        content = "﻿" + buffer.getvalue()
        filename = f"gpt-batch-{batch_id}.csv"
        return Response(
            content=content,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return app


def _unique_external_code(session: Session, model, prefix: str = "AW") -> tuple[str, str]:
    """生成不与该映射表冲突的外部码（极小概率碰撞，重试若干次）。

    model 为目标映射表 ORM 类（AskWhy / SMS 各自独立），prefix 区分业务线。
    """

    for _ in range(10):
        display, norm = generate_external_code(prefix)
        exists = (
            session.query(model.id)
            .filter(model.external_code_norm == norm)
            .first()
        )
        if exists is None:
            return display, norm
    raise HTTPException(status_code=500, detail="外部码生成冲突，请重试")


def _batch_mapping_op(session: Session, model, ids: list[int], action: str) -> int:
    """批量启用/停用/删除映射，返回实际影响的条数（接码卡密用）。

    已重发失效（reissued）的记录不允许再启用/停用，直接跳过；删除不受此限制。
    """

    if not ids:
        return 0
    rows = session.query(model).filter(model.id.in_(ids)).all()
    affected = 0
    for row in rows:
        if action == "delete":
            session.delete(row)
            affected += 1
        elif row.status != "reissued":
            row.status = "active" if action == "enable" else "disabled"
            affected += 1
    session.commit()
    return affected


def _sync_order(session: Session, order_payload: dict) -> None:
    """把 AskWhy 订单状态回写到本地记录。"""

    order_id = str(order_payload.get("id") or "").strip()
    if not order_id:
        return
    order = (
        session.query(AskWhyOrderModel)
        .filter(AskWhyOrderModel.askwhy_order_id == order_id)
        .first()
    )
    if order is None:
        return
    order.status = str(order_payload.get("status") or order.status)
    order.result_message = str(order_payload.get("resultMessage") or order.result_message or "")
    order.account_email = str(order_payload.get("email") or order.account_email or "")
    order.account_id = str(order_payload.get("accountId") or order.account_id or "")
    order.request_type = str(order_payload.get("requestType") or order.request_type or "")
    session.commit()
