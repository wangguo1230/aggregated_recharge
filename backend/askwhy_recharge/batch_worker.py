"""GPT 批量订阅后台执行器：单后台线程、全局串行，逐条提交并做到账确认。

严谨性约束（务必保持）：
- activate 非幂等且消耗库存：网络/解析异常导致结果未知时，一律标 NEEDS_REVIEW，
  绝不自动重试、绝不换卡重试，交由人工核对。
- 逐条原子认领（PENDING→SUBMITTING 条件 UPDATE，校验 rowcount）：即便多进程部署，
  同一条目也只会被一个执行者处理，不会重复提交。
- 逐条落库、可断点续跑：进程重启后只处理 PENDING；上轮崩在 SUBMITTING 的条目在
  续跑前统一转 NEEDS_REVIEW（疑似已提交），不自动重发。
- 充值成功后再调 /check 做到账确认；处理中(-1)有限次复查；全程不阻断其他条目。
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from datetime import datetime

from sqlalchemy import func

from .channels import AccountPrepareError, ProviderUnknownError, get_adapter
from .crypto import AskWhyCryptoError, FernetSecretCipher
from .db import SessionLocal
from .models import GptBatchItemModel, GptBatchModel, GptOrderModel
from .settings import AskWhySettings

logger = logging.getLogger(__name__)

# 「已用过、不可再投」的 cdkey 状态（批量条目侧）。
_USED_ITEM_STATUSES = ("SUCCEEDED", "PROCESSING", "SUBMITTING", "NEEDS_REVIEW")
# 账号「占用中」：尚未终结、即将/正在订阅的状态（用于跨批账号去重，避免撞 7 天防重浪费卡）。
_ACCOUNT_BUSY_STATUSES = ("PENDING", "SUBMITTING", "PROCESSING", "NEEDS_REVIEW")

_queue: "queue.Queue[int]" = queue.Queue()
_worker_thread: threading.Thread | None = None
_start_lock = threading.Lock()

_cipher: FernetSecretCipher | None = None
_settings: AskWhySettings | None = None


def cdkey_already_used(
    session,
    cdkey_fingerprint: str,
    channel: str,
    *,
    include_pending: bool = False,
    exclude_item_id: int | None = None,
) -> bool:
    """该 cdkey 在**同渠道**内是否已被占用、不可再投（不同渠道卡池独立，互不影响）。

    - include_pending=True（建批时）：连同其他批次里 PENDING（排队待执行）的也算占用。
    - exclude_item_id（执行时）：排除自身，做提交前的权威复检。
    - gpt86 额外检查单笔充值订单（GptOrderModel）；vip74 仅查批量条目。
    """
    statuses = (*_USED_ITEM_STATUSES, "PENDING") if include_pending else _USED_ITEM_STATUSES
    item_query = session.query(GptBatchItemModel.id).filter(
        GptBatchItemModel.cdkey_fingerprint == cdkey_fingerprint,
        GptBatchItemModel.channel == channel,
        GptBatchItemModel.status.in_(statuses),
    )
    if exclude_item_id is not None:
        item_query = item_query.filter(GptBatchItemModel.id != exclude_item_id)
    if item_query.first() is not None:
        return True
    # 同渠道的单笔充值订单也算占用（成功/进行中）。
    used_order = (
        session.query(GptOrderModel.id)
        .filter(
            GptOrderModel.card_fingerprint == cdkey_fingerprint,
            GptOrderModel.channel == channel,
            GptOrderModel.status.in_(("SUCCEEDED", "PROCESSING")),
        )
        .first()
    )
    return used_order is not None


def account_busy_elsewhere(session, session_fingerprint: str, channel: str) -> bool:
    """同一账号是否已在**同渠道**其他批次排队/执行中（PENDING/SUBMITTING/PROCESSING/NEEDS_REVIEW）。

    建批时跨批账号去重：避免两批同时冲同一账号撞上游 7 天防重而白白消耗卡。
    历史已成功(SUCCEEDED)不算占用，允许 7 天后续订。
    """
    return (
        session.query(GptBatchItemModel.id)
        .filter(
            GptBatchItemModel.session_fingerprint == session_fingerprint,
            GptBatchItemModel.channel == channel,
            GptBatchItemModel.status.in_(_ACCOUNT_BUSY_STATUSES),
        )
        .first()
        is not None
    )


# ==================== 生命周期 ====================
def configure_worker(cipher: FernetSecretCipher, settings: AskWhySettings) -> None:
    global _cipher, _settings
    _cipher = cipher
    _settings = settings


def start_worker() -> None:
    """启动后台执行线程（幂等），并恢复未完成的批次。"""
    global _worker_thread
    with _start_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return
        _worker_thread = threading.Thread(target=_run_loop, name="gpt-batch-worker", daemon=True)
        _worker_thread.start()
    _resume_unfinished()


def enqueue_batch(batch_id: int) -> None:
    _queue.put(int(batch_id))


def _resume_unfinished() -> None:
    """进程启动时恢复 PENDING/RUNNING 的批次；先把疑似中断（SUBMITTING）的条目转人工确认。"""
    session = SessionLocal()
    try:
        # 启动一刻没有任何条目真正在途，SUBMITTING 必是上轮崩溃残留 → 疑似已提交，禁止自动重发。
        stale = (
            session.query(GptBatchItemModel)
            .filter(GptBatchItemModel.status == "SUBMITTING")
            .all()
        )
        affected_batches: set[int] = set()
        for item in stale:
            item.status = "NEEDS_REVIEW"
            item.result_code = item.result_code or "provider.result_unknown"
            item.result_message = item.result_message or "上轮执行中断，结果未知，请人工核对后再处理"
            affected_batches.add(item.batch_id)
        # 存在结果未知条目的批次 → 暂停，等人工确认后再继续（与「结果未知就停下」一致）。
        for batch_id in affected_batches:
            batch = session.get(GptBatchModel, batch_id)
            if batch is not None and batch.status in ("PENDING", "RUNNING"):
                batch.status = "PAUSED"
                batch.paused_reason = batch.paused_reason or "执行中断，存在结果未知条目，请人工确认后再继续"
        if stale:
            session.commit()
            logger.warning("续跑：%s 条 SUBMITTING 转 NEEDS_REVIEW，相关 %s 个批次暂停", len(stale), len(affected_batches))

        # 仅恢复仍 PENDING/RUNNING 的批次；上面被置为 PAUSED 的不会自动续跑。
        rows = (
            session.query(GptBatchModel.id)
            .filter(GptBatchModel.status.in_(("PENDING", "RUNNING")))
            .order_by(GptBatchModel.id.asc())
            .all()
        )
    finally:
        session.close()
    for (batch_id,) in rows:
        _queue.put(int(batch_id))


def _run_loop() -> None:
    while True:
        batch_id = _queue.get()
        try:
            _process_batch(batch_id)
        except Exception:  # noqa: BLE001 - 单个批次异常不拖垮整个线程
            logger.exception("批量任务处理异常 batch_id=%s", batch_id)
        finally:
            _queue.task_done()


# 批内并发上限（保护上游）。每批实际并发取 min(本上限, 批次设置)。
_CONCURRENCY_CAP = 10


# ==================== 批次/条目处理 ====================
def _process_batch(batch_id: int) -> None:
    """处理一个批次：按批次设置的并发数起 N 个工作线程并发认领条目；批间仍串行（一次只跑一批）。"""
    assert _cipher is not None and _settings is not None
    session = SessionLocal()
    try:
        batch = session.get(GptBatchModel, batch_id)
        if batch is None or batch.status in ("DONE", "CANCELLED"):
            return
        if batch.cancel_requested:
            _finalize(session, batch, cancelled=True)
            return

        batch.status = "RUNNING"
        if batch.started_at is None:
            batch.started_at = datetime.utcnow()
        batch.paused_reason = ""  # 续跑清除上次暂停原因
        session.commit()

        force = bool(batch.force)
        concurrency = max(1, min(_CONCURRENCY_CAP, int(batch.concurrency or 1)))

        # 子线程间共享：stop（任一线程暂停/取消后通知其余停止认领）+ pause_lock（只置一次暂停原因）。
        stop = threading.Event()
        pause_lock = threading.Lock()
        if concurrency == 1:
            _item_loop(batch_id, force, stop, pause_lock)
        else:
            threads = [
                threading.Thread(
                    target=_item_loop,
                    args=(batch_id, force, stop, pause_lock),
                    name=f"gpt-batch-{batch_id}-{i}",
                    daemon=True,
                )
                for i in range(concurrency)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        # 收尾：用新事务读最新状态判定终态。
        session.rollback()
        if _is_cancelled(session, batch_id):
            _finalize(session, batch, cancelled=True)
            return
        batch = session.get(GptBatchModel, batch_id)
        if batch is not None and batch.status == "PAUSED":
            return  # 已被某条目置为暂停，保持暂停
        _finalize(session, batch, cancelled=False)
    finally:
        session.close()


def _item_loop(batch_id: int, force: bool, stop: threading.Event, pause_lock: threading.Lock) -> None:
    """单个工作线程：自有 DB session，循环原子认领并处理，直至无条目或收到停止信号。"""
    assert _settings is not None
    session = SessionLocal()
    try:
        interval = _settings.batch_item_interval_seconds
        while not stop.is_set():
            if _is_cancelled(session, batch_id):
                stop.set()
                break
            item = _claim_next(session, batch_id)
            if item is None:
                break
            action = _process_item(session, batch_id, force, item, stop, pause_lock)
            if action in ("pause", "cancelled"):
                stop.set()
                break
            if action == "stopped":
                break  # 已被其他线程停止，本条已回退
            if interval > 0:
                time.sleep(interval)
    except Exception:  # noqa: BLE001 - 单线程异常不影响其他线程/批次
        logger.exception("批量条目线程异常 batch_id=%s", batch_id)
    finally:
        session.close()


def _is_cancelled(session, batch_id: int) -> bool:
    """读取最新取消标记（上轮已 commit，新查询可见已提交变更）。"""
    return bool(
        session.query(GptBatchModel.cancel_requested).filter(GptBatchModel.id == batch_id).scalar()
    )


def _claim_next(session, batch_id: int) -> GptBatchItemModel | None:
    """原子认领下一条 PENDING：条件 UPDATE 校验 rowcount，确保同一条不被并发重复处理。"""
    while True:
        item = (
            session.query(GptBatchItemModel)
            .filter(
                GptBatchItemModel.batch_id == batch_id,
                GptBatchItemModel.status == "PENDING",
            )
            .order_by(GptBatchItemModel.seq.asc())
            .first()
        )
        if item is None:
            return None
        updated = (
            session.query(GptBatchItemModel)
            .filter(
                GptBatchItemModel.id == item.id,
                GptBatchItemModel.status == "PENDING",
            )
            .update(
                {
                    GptBatchItemModel.status: "SUBMITTING",
                    GptBatchItemModel.attempts: GptBatchItemModel.attempts + 1,
                },
                synchronize_session=False,
            )
        )
        session.commit()
        if updated == 1:
            session.refresh(item)
            return item
        # 被其他执行者抢走，继续找下一条。


def _process_item(
    session,
    batch_id: int,
    force: bool,
    item: GptBatchItemModel,
    stop: threading.Event,
    pause_lock: threading.Lock,
) -> str:
    """处理单条，返回动作：'advance' / 'pause'(整批暂停) / 'cancelled'(整批取消) / 'stopped'(被停止已回退)。"""
    adapter = get_adapter(item.channel)
    if adapter is None:
        item.status = "FAILED"
        item.result_code = "config.channel_unknown"
        item.result_message = f"未知渠道：{item.channel}"
        session.commit()
        _set_pause(session, batch_id, item, item.result_message, pause_lock)
        return "pause"

    # 提交前权威复检（同渠道）：若同卡已被其他条目占用，跳过绝不重复投。
    if cdkey_already_used(session, item.cdkey_fingerprint, item.channel, exclude_item_id=item.id):
        item.status = "SKIPPED"
        item.result_code = "cdk.already_used"
        item.result_message = "该卡密已被其他条目使用，跳过避免重复提交"
        session.commit()
        return "advance"

    try:
        cdkey = _cipher.decrypt(item.cdkey_encrypted)
        account = _cipher.decrypt(item.session_info_encrypted)
    except AskWhyCryptoError as exc:
        item.status = "FAILED"
        item.result_code = "server.decrypt_failed"
        item.result_message = f"解密失败：{exc}"
        session.commit()
        _set_pause(session, batch_id, item, item.result_message, pause_lock)
        return "pause"

    # 提交前账号准备（一次性）：如 86 账号行 rt→at→拼 session_info。失败=单条跳过（卡密未消耗）。
    # rt 轮转：换到新 rt 后通过 on_rotate **立即落库**，再去取账号信息，最大限度避免新 rt 丢失。
    def _persist_rotated(new_line: str) -> None:
        item.session_info_encrypted = _cipher.encrypt(new_line)
        session.commit()

    try:
        account, _updated_line = adapter.prepare(account, on_rotate=_persist_rotated)
    except AccountPrepareError as exc:
        if exc.updated_account_line:
            _persist_rotated(exc.updated_account_line)  # 兜底：确保新 rt 落库
        item.status = "FAILED"
        item.result_code = "account.prepare_failed"
        item.result_message = str(exc)[:255]
        session.commit()
        return "advance"

    # 记录实际提交给上游的内容（86 账号行模式 = 拼接好的 session_info），供导出/对账。
    item.built_session_encrypted = _cipher.encrypt(account)
    session.commit()

    retry_interval = max(1, _settings.batch_stock_retry_interval_seconds)
    while True:
        # 暂停/取消：重试等待中（未消耗卡）→ 回退为 PENDING，交由续跑/取消处理，避免卡在 SUBMITTING。
        if stop.is_set() or _is_cancelled(session, batch_id):
            if _is_cancelled(session, batch_id):
                stop.set()
            item.status = "PENDING"
            item.result_message = "（暂停/取消时仍在等待重试，已回退待继续）"
            session.commit()
            return "stopped"

        try:
            outcome = adapter.submit(cdkey, account, force)
        except ProviderUnknownError as exc:
            # 结果未知：上游可能已扣卡/已订阅，也可能没有。禁止自动重试/换卡 → 人工核对 + 暂停。
            item.status = "NEEDS_REVIEW"
            item.result_code = "provider.network_unknown"
            item.result_message = f"提交异常，结果未知：{exc}"
            session.commit()
            _set_pause(session, batch_id, item, item.result_message, pause_lock)
            return "pause"

        # 可重试类（缺货/冷却/限流/临时异常）：按固定间隔一直重刷，不封顶（上游未消耗卡）。
        if outcome.kind == "transient":
            item.stock_retries = (item.stock_retries or 0) + 1
            item.use_status = outcome.use_status
            item.result_code = outcome.code or "provider.transient"
            item.result_message = f"{outcome.message or '暂不可用，等待重试中'}（已重试 {item.stock_retries} 次）"
            session.commit()
            time.sleep(retry_interval)
            continue
        break

    item.use_status = outcome.use_status
    item.result_code = outcome.code
    item.result_message = outcome.message
    item.account = outcome.account
    item.completed_at = outcome.completed_at

    # 充值完确认到账（处理中 → 有限次复查；成功 → 取快照）。
    if outcome.kind == "processing":
        refined = adapter.recheck(cdkey)
        if refined.use_status is not None:
            item.use_status = refined.use_status
        if refined.account:
            item.account = refined.account
        if refined.completed_at:
            item.completed_at = refined.completed_at
        if refined.snapshot:
            item.subscription_json = refined.snapshot
        final_kind = refined.kind
    elif outcome.kind == "success":
        item.subscription_json = adapter.confirm(cdkey) or {}
        final_kind = "success"
    else:
        final_kind = outcome.kind  # item_fail / systemic

    item.status = {"success": "SUCCEEDED", "processing": "PROCESSING"}.get(final_kind, "FAILED")
    session.commit()

    if item.status != "FAILED":
        return "advance"

    # 失败分档：系统性 → 暂停整批；单账号自身失败 → 记 FAILED 跳过继续。
    if final_kind == "systemic":
        _set_pause(session, batch_id, item, f"系统异常：{item.result_message or item.result_code}", pause_lock)
        return "pause"

    # 可选熔断：累计失败过多则暂停（疑似系统性问题）；阈值 0=关闭。
    threshold = _settings.batch_failure_pause_threshold
    if threshold > 0:
        failed_count = (
            session.query(func.count(GptBatchItemModel.id))
            .filter(GptBatchItemModel.batch_id == batch_id, GptBatchItemModel.status == "FAILED")
            .scalar()
            or 0
        )
        if failed_count >= threshold:
            _set_pause(session, batch_id, item, f"失败条目达到 {failed_count}，已暂停（疑似系统性问题）", pause_lock)
            return "pause"

    return "advance"


def _set_pause(session, batch_id: int, item: GptBatchItemModel, reason: str, pause_lock: threading.Lock) -> None:
    """并发安全地把批次置为暂停（只置一次原因）：用直接 UPDATE 避免身份映射缓存读到旧状态。"""
    with pause_lock:
        current = (
            session.query(GptBatchModel.status).filter(GptBatchModel.id == batch_id).scalar()
        )
        if current not in ("PAUSED", "CANCELLED", "DONE"):
            session.query(GptBatchModel).filter(GptBatchModel.id == batch_id).update(
                {
                    GptBatchModel.status: "PAUSED",
                    GptBatchModel.paused_reason: f"第 {item.seq} 条：{reason}"[:255],
                },
                synchronize_session=False,
            )
        session.commit()


def _finalize(session, batch: GptBatchModel, cancelled: bool) -> None:
    if cancelled:
        session.query(GptBatchItemModel).filter(
            GptBatchItemModel.batch_id == batch.id,
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
    else:
        batch.status = "DONE"
    if batch.finished_at is None:
        batch.finished_at = datetime.utcnow()
    session.commit()
