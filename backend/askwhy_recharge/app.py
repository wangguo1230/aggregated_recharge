"""AskWhy 充值服务 FastAPI 应用。

公开接口（/api/askwhy/*）面向客户：客户提交的是「外部码」，后端经映射表解析成
真实 AskWhy 卡密再转发，响应里剥离真实卡，客户看不到真实卡密与套餐前缀。
管理接口（/api/askwhy/admin/*）需口令鉴权：录入真实卡并自动生成外部码、管理映射。

充值流程：校验卡密(外部码) → 校验 Session JSON → 充值 → 查进度 → 查订阅。
真实卡密与 Session JSON 在创建订单时加密落库（PostgreSQL）。
"""

from __future__ import annotations

import hmac
import logging

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .client import AskWhyApiError, AskWhyClient
from .codes import generate_external_code, normalize_external_code
from .crypto import AskWhyCryptoError, FernetSecretCipher, fingerprint
from .db import get_db_session, init_askwhy_db
from .gift_client import GiftApiError, GiftClient
from .models import (
    AskWhyCardMappingModel,
    AskWhyOrderModel,
    ClaudeCardMappingModel,
    ClaudeOrderModel,
    SmsCardMappingModel,
)
from .schemas import (
    BatchMappingRequest,
    CardStatusRequest,
    ClaudeActivateRequest,
    CreateOrderRequest,
    ImportMappingsRequest,
    LookupMappingsRequest,
    MappingStatusRequest,
    SmsFetchRequest,
    SmsImportMappingsRequest,
    SmsVerifyRequest,
    SubscriptionRequest,
    VerifyCardRequest,
    VerifyTokenRequest,
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

    # ==================== Claude Pro 充值（Gift 上游）====================
    def resolve_claude_mapping(session: Session, external_input: str) -> ClaudeCardMappingModel | None:
        norm = normalize_external_code(external_input)
        if not norm:
            return None
        return (
            session.query(ClaudeCardMappingModel)
            .filter(
                ClaudeCardMappingModel.external_code_norm == norm,
                ClaudeCardMappingModel.status == "active",
            )
            .first()
        )

    @app.post("/api/claude/card/verify")
    def claude_verify(payload: VerifyCardRequest, session: Session = Depends(get_db_session)) -> dict:
        """外部码查卡：解析成真实 cdkey 调上游 check，回包剥离真实卡（用外部码替换）。"""
        mapping = resolve_claude_mapping(session, payload.card_code)
        if mapping is None:
            return _fail("卡密不存在或不可用")
        try:
            result = gift_client.check(cipher.decrypt(mapping.real_card_encrypted))
        except (GiftApiError, AskWhyCryptoError) as exc:
            return _fail(str(exc))
        if not result.get("success"):
            return _fail(str(result.get("msg") or "卡密不可用"))
        data = result.get("data") if isinstance(result.get("data"), dict) else {}
        return {
            "ok": True,
            "message": str(result.get("msg") or ""),
            "card": {
                "code": mapping.external_code,
                "giftName": str(data.get("gift_name") or mapping.gift_name or ""),
                "app": str(data.get("app") or mapping.app or "claude"),
                "useStatus": data.get("use_status"),
                "statusHint": str(data.get("status_hint") or ""),
                "account": str(data.get("account") or ""),
                "completedAt": str(data.get("completed_at") or ""),
                "inCooldown": bool(data.get("in_cooldown", False)),
                "cooldownRemaining": data.get("cooldown_remaining") or 0,
            },
        }

    @app.post("/api/claude/activate")
    def claude_activate(
        payload: ClaudeActivateRequest,
        request: Request,
        session: Session = Depends(get_db_session),
    ) -> dict:
        """外部码 + uid 提交激活：解析真实 cdkey 调上游 activate，落库订单，回包剥离真实卡。"""
        uid = payload.uid.strip()
        mapping = resolve_claude_mapping(session, payload.card_code)
        if mapping is None:
            return _fail("卡密不存在或不可用")
        try:
            real_cdkey = cipher.decrypt(mapping.real_card_encrypted)
        except AskWhyCryptoError as exc:
            return _fail(str(exc))
        try:
            result = gift_client.activate(real_cdkey, uid)
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

        # 按外部码 upsert 订单，避免同一卡密重复提交产生多行。
        order = (
            session.query(ClaudeOrderModel)
            .filter(ClaudeOrderModel.external_code == mapping.external_code)
            .order_by(ClaudeOrderModel.id.desc())
            .first()
        )
        if order is None:
            order = ClaudeOrderModel(
                external_code=mapping.external_code,
                card_code_encrypted=mapping.real_card_encrypted,
                card_fingerprint=mapping.real_card_fingerprint,
                card_last4=mapping.real_card_last4,
            )
            session.add(order)
        order.uid = uid
        order.gift_name = str(data.get("gift_name") or mapping.gift_name or "")
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
                "externalCode": mapping.external_code,
                "giftName": order.gift_name,
                "useStatus": use_status,
                "account": order.account,
                "completedAt": order.completed_at,
            },
        }

    # ---- Claude 卡密管理（复用同一管理口令）----
    @app.post("/api/claude/admin/mappings/import", dependencies=[Depends(require_admin)])
    def claude_import_mappings(payload: ImportMappingsRequest, session: Session = Depends(get_db_session)) -> dict:
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
                session.query(ClaudeCardMappingModel)
                .filter(ClaudeCardMappingModel.real_card_fingerprint == fp)
                .first()
            )
            if existing is not None:
                results.append(
                    {
                        "realCard": real,
                        "externalCode": existing.external_code,
                        "giftName": existing.gift_name,
                        "status": "exists",
                        "message": "该 cdkey 已存在映射",
                    }
                )
                continue

            # check 取商品信息（只读）；失败不阻断录入。
            gift_name = app_name = ""
            check_message = ""
            check_ok = False
            try:
                checked = gift_client.check(real)
                check_ok = bool(checked.get("success"))
                check_message = str(checked.get("msg") or "")
                cdata = checked.get("data") if isinstance(checked.get("data"), dict) else {}
                gift_name = str(cdata.get("gift_name") or "")
                app_name = str(cdata.get("app") or "")
            except GiftApiError as exc:
                check_message = str(exc)

            display, norm = _unique_external_code(session, ClaudeCardMappingModel, "CL")
            mapping = ClaudeCardMappingModel(
                external_code=display,
                external_code_norm=norm,
                real_card_encrypted=cipher.encrypt(real),
                real_card_fingerprint=fp,
                real_card_last4=real[-4:],
                gift_name=gift_name,
                app=app_name or "claude",
                status="active",
                note=note,
            )
            session.add(mapping)
            session.commit()
            results.append(
                {
                    "realCard": real,
                    "externalCode": display,
                    "giftName": gift_name,
                    "status": "created",
                    "message": "已生成" if check_ok else f"已生成（上游校验未通过：{check_message or '未知'}）",
                    "checkOk": check_ok,
                }
            )
        created = sum(1 for r in results if r["status"] == "created")
        return {"ok": True, "created": created, "total": len(results), "results": results}

    @app.get("/api/claude/admin/mappings", dependencies=[Depends(require_admin)])
    def claude_list_mappings(
        q: str = Query("", max_length=64),
        limit: int = Query(500, ge=1, le=2000),
        session: Session = Depends(get_db_session),
    ) -> dict:
        query = session.query(ClaudeCardMappingModel)
        keyword = q.strip()
        if keyword:
            norm = normalize_external_code(keyword)
            query = query.filter(ClaudeCardMappingModel.external_code_norm.like(f"%{norm}%"))
        rows = query.order_by(ClaudeCardMappingModel.id.desc()).limit(limit).all()
        items = []
        for row in rows:
            try:
                real_card = cipher.decrypt(row.real_card_encrypted) if row.real_card_encrypted else ""
            except AskWhyCryptoError:
                real_card = ""
            items.append(
                {
                    "id": row.id,
                    "externalCode": row.external_code,
                    "realCard": real_card,
                    "giftName": row.gift_name,
                    "app": row.app,
                    "status": row.status,
                    "note": row.note,
                    "createdAt": row.created_at.isoformat() if row.created_at else "",
                }
            )
        return {"ok": True, "count": len(items), "items": items}

    @app.post("/api/claude/admin/mappings/lookup", dependencies=[Depends(require_admin)])
    def claude_lookup_mappings(payload: LookupMappingsRequest, session: Session = Depends(get_db_session)) -> dict:
        """批量外部码反查原始 cdkey：保留输入顺序，精确匹配，去重。"""
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
                session.query(ClaudeCardMappingModel)
                .filter(ClaudeCardMappingModel.external_code_norm == norm)
                .first()
            )
            if row is None:
                results.append({"input": code, "found": False, "externalCode": "", "realCard": ""})
                continue
            try:
                real_card = cipher.decrypt(row.real_card_encrypted) if row.real_card_encrypted else ""
            except AskWhyCryptoError:
                real_card = ""
            results.append(
                {
                    "input": code,
                    "found": True,
                    "externalCode": row.external_code,
                    "realCard": real_card,
                    "giftName": row.gift_name,
                    "status": row.status,
                }
            )
        found = sum(1 for r in results if r["found"])
        return {"ok": True, "found": found, "total": len(results), "results": results}

    @app.patch("/api/claude/admin/mappings/{mapping_id}", dependencies=[Depends(require_admin)])
    def claude_update_mapping(
        payload: MappingStatusRequest,
        mapping_id: int = Path(..., ge=1),
        session: Session = Depends(get_db_session),
    ) -> dict:
        row = session.get(ClaudeCardMappingModel, mapping_id)
        if row is None:
            return _fail("映射不存在")
        if row.status == "reissued":
            return _fail("该外部码已重发并失效，不可再变更状态")
        row.status = payload.status
        session.commit()
        return {"ok": True}

    @app.post("/api/claude/admin/mappings/{mapping_id}/reissue", dependencies=[Depends(require_admin)])
    def claude_reissue_mapping(
        mapping_id: int = Path(..., ge=1),
        session: Session = Depends(get_db_session),
    ) -> dict:
        """重新生成外部码：旧码置为 reissued 失效，新建一条指向同一真实 cdkey 的 active 记录。"""
        old = session.get(ClaudeCardMappingModel, mapping_id)
        if old is None:
            return _fail("映射不存在")
        if old.status == "reissued":
            return _fail("该外部码已重发，请对最新的外部码操作")
        display, norm = _unique_external_code(session, ClaudeCardMappingModel, "CL")
        fresh = ClaudeCardMappingModel(
            external_code=display,
            external_code_norm=norm,
            real_card_encrypted=old.real_card_encrypted,
            real_card_fingerprint=old.real_card_fingerprint,
            real_card_last4=old.real_card_last4,
            gift_name=old.gift_name,
            app=old.app,
            status="active",
            note=old.note,
        )
        old.status = "reissued"
        session.add(fresh)
        session.commit()
        return {"ok": True, "externalCode": display}

    @app.delete("/api/claude/admin/mappings/{mapping_id}", dependencies=[Depends(require_admin)])
    def claude_delete_mapping(
        mapping_id: int = Path(..., ge=1),
        session: Session = Depends(get_db_session),
    ) -> dict:
        row = session.get(ClaudeCardMappingModel, mapping_id)
        if row is None:
            return _fail("映射不存在")
        session.delete(row)
        session.commit()
        return {"ok": True}

    @app.post("/api/claude/admin/mappings/batch", dependencies=[Depends(require_admin)])
    def claude_batch_mappings(
        payload: BatchMappingRequest,
        session: Session = Depends(get_db_session),
    ) -> dict:
        """批量启用/停用/删除 Claude 卡密映射。"""
        affected = _batch_mapping_op(session, ClaudeCardMappingModel, payload.ids, payload.action)
        return {"ok": True, "affected": affected}

    @app.get("/api/claude/admin/orders", dependencies=[Depends(require_admin)])
    def claude_list_orders(
        q: str = Query("", max_length=120),
        limit: int = Query(200, ge=1, le=1000),
        session: Session = Depends(get_db_session),
    ) -> dict:
        query = session.query(ClaudeOrderModel)
        keyword = q.strip()
        if keyword:
            like = f"%{keyword}%"
            query = query.filter(
                (ClaudeOrderModel.external_code.like(like))
                | (ClaudeOrderModel.uid.like(like))
                | (ClaudeOrderModel.account.like(like))
            )
        rows = query.order_by(ClaudeOrderModel.id.desc()).limit(limit).all()
        items = []
        for row in rows:
            try:
                real_card = cipher.decrypt(row.card_code_encrypted) if row.card_code_encrypted else ""
            except AskWhyCryptoError:
                real_card = ""
            items.append(
                {
                    "id": row.id,
                    "externalCode": row.external_code,
                    "realCard": real_card,
                    "uid": row.uid,
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
    """批量启用/停用/删除映射，返回实际影响的条数（接码卡密、Claude 卡密通用）。

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
