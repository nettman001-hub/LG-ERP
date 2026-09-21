import os
import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Deque, Dict, List, Optional, Tuple

import requests

from erp_client import ERPClient, ERPSession, format_production_plan_details
from price_compare import fetch_danawa_lowest_price


DEFAULT_INVENTORY_BRIDGE_BASE_URL = (
    os.environ.get("INVENTORY_BRIDGE_BASE_URL", "").strip()
    or "http://unione24.co.kr/api/inventory"
).rstrip("/")
DEFAULT_INVENTORY_BRIDGE_TOKEN = os.environ.get("INVENTORY_BRIDGE_TOKEN", "").strip()


def _read_poll_interval() -> float:
    raw = os.environ.get("INVENTORY_BRIDGE_POLL_SECONDS", "").strip()
    if not raw:
        return 2.5
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 2.5


DEFAULT_INVENTORY_BRIDGE_POLL_SECONDS = _read_poll_interval()


def _now_text(ts: Optional[float] = None) -> str:
    if ts is None:
        ts = time.time()
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S")


def _normalize_model_token(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def _model_aliases(value: str) -> List[str]:
    aliases: List[str] = []
    seen: set[str] = set()

    raw = (value or "").strip().upper()
    if not raw:
        return aliases

    for candidate in (raw, raw.split(".", 1)[0], raw.split("-", 1)[0], raw.split(" ", 1)[0]):
        normalized = _normalize_model_token(candidate)
        if len(normalized) < 5 or normalized in seen:
            continue
        seen.add(normalized)
        aliases.append(normalized)

    return aliases


def extract_model_candidates(query_text: str) -> List[str]:
    candidates: List[str] = []
    seen: set[str] = set()

    for token in re.findall(r"[A-Z0-9][A-Z0-9/_\-]{4,}", (query_text or "").upper()):
        normalized = _normalize_model_token(token)
        if len(normalized) < 5:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        candidates.append(normalized)

    compact = _normalize_model_token(query_text)
    if len(compact) >= 5 and compact not in seen:
        candidates.append(compact)

    return candidates


def clone_erp_session(source: ERPSession) -> ERPSession:
    cloned = ERPSession()
    cloned.session.headers.clear()
    cloned.session.headers.update(dict(source.session.headers))
    cloned.session.verify = source.session.verify
    for cookie in source.session.cookies:
        cloned.session.cookies.set(
            cookie.name,
            cookie.value,
            domain=cookie.domain,
            path=cookie.path,
        )

    cloned.user_id = source.user_id
    cloned.password = source.password
    cloned.internal_user_id = source.internal_user_id
    cloned.user_id_candidates = list(source.user_id_candidates)
    cloned.employee_ssn = source.employee_ssn
    cloned.channel_code = source.channel_code
    cloned.comp_code = source.comp_code
    cloned.inventory_wh_id = source.inventory_wh_id
    cloned.b2b_bridge_form = dict(source.b2b_bridge_form)
    cloned._logged_in = source._logged_in
    cloned._pre_step_token = source._pre_step_token
    cloned._user_hp_no = source._user_hp_no
    cloned._opt_key = source._opt_key
    cloned._comp_type = source._comp_type
    return cloned


def _pick_best_model(candidate: str, models: List[dict]) -> Tuple[str, str]:
    if not models:
        return "", ""

    target = _normalize_model_token(candidate)
    ranked: List[Tuple[int, str]] = []
    for model in models:
        item_cd = str(model.get("ITEM_CD", "")).strip()
        normalized = _normalize_model_token(item_cd)
        score = 99
        if normalized == target:
            score = 0
        elif normalized.startswith(target):
            score = 1
        elif target and target in normalized:
            score = 2
        ranked.append((score, item_cd))

    ranked.sort(key=lambda item: (item[0], item[1]))
    selected = ranked[0][1]
    note = ""
    if _normalize_model_token(selected) != target:
        note = f"\uc785\ub825 \ud488\ubc88 {candidate} \uae30\uc900\uc73c\ub85c {selected} \ubaa8\ub378\uc744 \uc120\ud0dd\ud574 \uc870\ud68c\ud588\uc2b5\ub2c8\ub2e4."
    return selected, note


def _pick_best_model(candidate: str, models: List[dict]) -> Tuple[str, str]:
    if not models:
        return "", ""

    target = _normalize_model_token(candidate)
    ranked: List[Tuple[int, str]] = []
    for model in models:
        item_cd = str(model.get("ITEM_CD", "")).strip()
        normalized = _normalize_model_token(item_cd)
        score = 99
        if normalized == target:
            score = 0
        elif normalized.startswith(target):
            score = 1
        elif target and target in normalized:
            score = 2
        ranked.append((score, item_cd))

    ranked.sort(key=lambda item: (item[0], item[1]))
    selected = ranked[0][1]
    note = ""
    if _normalize_model_token(selected) != target:
        note = f"입력 품번 {candidate} 기준으로 {selected} 모델을 선택해 조회했습니다."
    return selected, note


def _format_int(value: Optional[int]) -> str:
    if value is None:
        return "확인 불가"
    return f"{value:,}"


def _format_int(value: Optional[int]) -> str:
    if value is None:
        return "\ud655\uc778 \ubd88\uac00"
    return f"{value:,}"


def _format_int(value: Optional[int]) -> str:
    if value is None:
        return "확인 불가"
    return f"{value:,}"


def _lookup_workbook_supply_price(
    workbook_price_index: Optional[Dict[str, Dict[str, object]]],
    *,
    selected_item_cd: str,
    candidates: List[str],
) -> Tuple[Optional[int], str]:
    if not workbook_price_index:
        return None, ""

    lookup_keys: List[str] = []
    seen: set[str] = set()
    for value in [selected_item_cd, *candidates]:
        for alias in _model_aliases(value):
            if alias in seen:
                continue
            seen.add(alias)
            lookup_keys.append(alias)

    for key in lookup_keys:
        row = workbook_price_index.get(key)
        if not row:
            continue
        supply_price = row.get("supply_price")
        if supply_price is None:
            continue
        try:
            return int(float(str(supply_price))), str(row.get("model_name", "")).strip()
        except (TypeError, ValueError):
            continue

    return None, ""


def build_result_text(
    query_text: str,
    erp_template: Optional[ERPSession],
    workbook_price_index: Optional[Dict[str, Dict[str, object]]] = None,
) -> Tuple[str, str]:
    if not erp_template or not erp_template.is_session_valid():
        return (
            "FAIL",
            "ERP 로그인이 되어 있지 않아 조회할 수 없습니다. PC에서 ERP 로그인 후 다시 시도해 주세요.",
        )

    candidates = extract_model_candidates(query_text)
    if not candidates:
        return (
            "FAIL",
            f"문의 내용에서 품번을 찾지 못했습니다. 문의 내용: {query_text}",
        )

    worker_session = clone_erp_session(erp_template)
    erp_client = ERPClient(worker_session)

    selected_lookup = None
    last_lookup_error = ""
    for candidate in candidates:
        full_models = erp_client.query_full_model(candidate)
        last_lookup_error = erp_client.last_error.strip()
        if last_lookup_error:
            return (
                "FAIL",
                f"ERP 품번 조회 중 오류가 발생했습니다. 입력 품번: {candidate}\n사유: {last_lookup_error}",
            )
        if not full_models:
            continue

        selected_lookup = erp_client.select_best_inventory_model(candidate, full_models)
        if selected_lookup:
            break

    if not selected_lookup:
        return (
            "FAIL",
            erp_client.last_error or f"ERP에서 조회 가능한 품번을 찾지 못했습니다. 문의 내용: {query_text}",
        )

    selected_item_cd = str(selected_lookup.model.get("ITEM_CD", "")).strip()
    inventory_rows = selected_lookup.inventory_rows
    inventory_error = selected_lookup.inventory_error
    production_plan = selected_lookup.production_plan
    production_error = selected_lookup.production_error
    workbook_supply_price, workbook_model_name = _lookup_workbook_supply_price(
        workbook_price_index,
        selected_item_cd=selected_item_cd,
        candidates=candidates,
    )
    price_info = {}
    price_info_error = ""
    supply_price = workbook_supply_price
    if supply_price is None:
        price_info = erp_client.query_price_info(selected_item_cd)
        price_info_error = erp_client.last_error.strip()
        supply_price = price_info.get("supply_price") or None

    price_error = ""
    danawa_price: Optional[int] = None
    try:
        danawa_price, _search_keyword, _url = fetch_danawa_lowest_price(selected_item_cd)
    except Exception as exc:
        price_error = str(exc)

    inventory_parts: List[str] = []
    for row in inventory_rows:
        qty_raw = row.get("AVAILABLE_QTY", "0")
        try:
            qty = int(qty_raw)
        except (TypeError, ValueError):
            qty = 0
        if qty <= 0:
            continue
        org_name = str(row.get("INVENTORY_ORG_NAME", "")).strip() or "창고"
        inventory_parts.append(f"• {org_name}: {qty}대")

    lines = [f"📦 [{selected_item_cd}] 조회 결과"]
    if selected_lookup.selection_note:
        lines.append(f"ℹ️ {selected_lookup.selection_note}")
    if workbook_supply_price is not None and workbook_model_name:
        lines.append(f"🔖 가격표 모델: {workbook_model_name}")

    lines.append("")
    lines.append("🏢 [재고 현황]")
    if inventory_error and not inventory_rows:
        lines.append(f"❌ 조회 실패 ({inventory_error})")
    else:
        lines.append(f"- 총 합계: {selected_lookup.inventory_total}대")
        if inventory_parts:
            lines.extend(inventory_parts)
        else:
            lines.append("- 가용 재고 없음")

    lines.append("")
    lines.append("📅 [생산 계획]")
    if production_error:
        lines.append(f"❌ 조회 실패 ({production_error})")
    else:
        if production_plan.days:
            for detail_line in format_production_plan_details(production_plan):
                lines.append(f"- {detail_line}")
        else:
            lines.append("- 계획된 수량 없음")

    lines.append("")
    lines.append("💰 [가격 정보]")
    if supply_price is None:
        price_status = f" ({price_info_error})" if price_info_error else ""
        lines.append(f"- 공급가: 확인 불가{price_status}")
    else:
        lines.append(f"- 공급가: {_format_int(supply_price)}원")

    if danawa_price is None:
        danawa_status = f" ({price_error})" if price_error else ""
        lines.append(f"- 다나와: 확인 불가{danawa_status}")
    else:
        lines.append(f"- 다나와: {_format_int(danawa_price)}원")

    return "DONE", "\n".join(lines)


@dataclass(frozen=True)
class QueueJob:
    id: int
    kakao_user_id: str
    query_text: str
    status: str
    created_at: str


@dataclass
class QueueStatusSnapshot:
    bridge_url: str
    running: bool
    bridge_ok: bool
    erp_ready: bool
    poll_interval_seconds: float
    last_poll_at: Optional[float]
    last_poll_ok_at: Optional[float]
    last_error: str
    remote_waiting_count: int
    queued_count: int
    inflight_count: int
    completed_count: int
    failed_count: int
    worker_status: str
    current_job_text: str
    recent_events: List[str] = field(default_factory=list)


class InventoryBridgeClient:
    def __init__(self, base_url: str, *, token: str = "", timeout: float = 5.0):
        self.base_url = (base_url or "").strip().rstrip("/")
        self.token = (token or "").strip()
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "LG-ERP-Inventory-Worker/1.0",
        })

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.token:
            headers["X-Bridge-Token"] = self.token
        return headers

    def fetch_waiting(self, *, limit: int = 5) -> Tuple[List[QueueJob], int]:
        response = self.session.get(
            f"{self.base_url}/inventory_queue_pull.php",
            params={"limit": limit},
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(str(payload.get("error", "브리지 조회 실패")))

        jobs: List[QueueJob] = []
        for row in payload.get("items", []):
            try:
                jobs.append(
                    QueueJob(
                        id=int(row.get("id", 0)),
                        kakao_user_id=str(row.get("kakao_user_id", "")),
                        query_text=str(row.get("query_text", "")),
                        status=str(row.get("status", "")),
                        created_at=str(row.get("created_at", "")),
                    )
                )
            except (TypeError, ValueError):
                continue

        waiting_count = int(payload.get("waiting_count", len(jobs)))
        return jobs, waiting_count

    def update_result(self, job_id: int, status: str, result_text: str) -> None:
        response = self.session.post(
            f"{self.base_url}/inventory_queue_update.php",
            json={
                "id": job_id,
                "status": status,
                "result_text": result_text,
            },
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(str(payload.get("error", "결과 업데이트 실패")))


class InventoryQueueController:
    def __init__(
        self,
        *,
        base_url: str = DEFAULT_INVENTORY_BRIDGE_BASE_URL,
        token: str = DEFAULT_INVENTORY_BRIDGE_TOKEN,
        poll_interval_seconds: float = DEFAULT_INVENTORY_BRIDGE_POLL_SECONDS,
        fetch_limit: int = 5,
    ) -> None:
        self.client = InventoryBridgeClient(base_url, token=token)
        self.poll_interval_seconds = max(1.0, float(poll_interval_seconds))
        self.fetch_limit = max(1, int(fetch_limit))

        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._queue_condition = threading.Condition(self._lock)
        self._queued_jobs: Deque[QueueJob] = deque()
        self._known_job_ids: set[int] = set()
        self._inflight_job_ids: set[int] = set()
        self._recent_events: Deque[str] = deque(maxlen=30)
        self._erp_template: Optional[ERPSession] = None
        self._workbook_price_index: Dict[str, Dict[str, object]] = {}

        self._bridge_ok = False
        self._last_poll_at: Optional[float] = None
        self._last_poll_ok_at: Optional[float] = None
        self._last_error = ""
        self._remote_waiting_count = 0
        self._completed_count = 0
        self._failed_count = 0
        self._worker_status = "대기 중"
        self._current_job_text = "-"

        self._poll_thread = threading.Thread(target=self._poll_loop, name="inventory-queue-poll", daemon=True)
        self._worker_thread = threading.Thread(target=self._worker_loop, name="inventory-queue-worker", daemon=True)

    def start(self) -> None:
        self._append_event("재고 큐 폴링을 시작했습니다.")
        self._poll_thread.start()
        self._worker_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        with self._queue_condition:
            self._queue_condition.notify_all()
        self._poll_thread.join(timeout=2.0)
        self._worker_thread.join(timeout=2.0)

    def sync_erp_session(self, session: Optional[ERPSession]) -> None:
        with self._lock:
            if session and session.is_session_valid():
                self._erp_template = clone_erp_session(session)
                self._append_event_locked("ERP 세션을 백그라운드 작업과 동기화했습니다.")
            else:
                self._erp_template = None
                self._append_event_locked("ERP 세션이 준비될 때까지 백그라운드 조회를 대기합니다.")

    def sync_workbook_price_index(self, index: Optional[Dict[str, Dict[str, object]]]) -> None:
        with self._lock:
            self._workbook_price_index = dict(index or {})
            if self._workbook_price_index:
                self._append_event_locked(f"워크북 가격 인덱스를 동기화했습니다: {len(self._workbook_price_index)}행")
            else:
                self._append_event_locked("워크북 가격 인덱스가 비어 있어 ERP 가격 조회만 사용합니다.")

    def snapshot(self) -> QueueStatusSnapshot:
        with self._lock:
            return QueueStatusSnapshot(
                bridge_url=self.client.base_url,
                running=not self._stop_event.is_set(),
                bridge_ok=self._bridge_ok,
                erp_ready=bool(self._erp_template and self._erp_template.is_session_valid()),
                poll_interval_seconds=self.poll_interval_seconds,
                last_poll_at=self._last_poll_at,
                last_poll_ok_at=self._last_poll_ok_at,
                last_error=self._last_error,
                remote_waiting_count=self._remote_waiting_count,
                queued_count=len(self._queued_jobs),
                inflight_count=len(self._inflight_job_ids),
                completed_count=self._completed_count,
                failed_count=self._failed_count,
                worker_status=self._worker_status,
                current_job_text=self._current_job_text,
                recent_events=list(self._recent_events),
            )

    def _append_event(self, message: str) -> None:
        with self._lock:
            self._append_event_locked(message)

    def _append_event_locked(self, message: str) -> None:
        self._recent_events.appendleft(f"[{_now_text()}] {message}")

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            poll_started_at = time.time()
            try:
                jobs, waiting_count = self.client.fetch_waiting(limit=self.fetch_limit)
                new_count = 0
                with self._queue_condition:
                    self._bridge_ok = True
                    self._last_error = ""
                    self._last_poll_at = poll_started_at
                    self._last_poll_ok_at = poll_started_at
                    self._remote_waiting_count = waiting_count
                    for job in jobs:
                        if job.id in self._known_job_ids or job.id in self._inflight_job_ids:
                            continue
                        self._queued_jobs.append(job)
                        self._known_job_ids.add(job.id)
                        new_count += 1
                    if new_count:
                        self._append_event_locked(f"새 원격 요청 {new_count}건을 큐에 적재했습니다.")
                    self._queue_condition.notify_all()
            except Exception as exc:
                with self._queue_condition:
                    self._bridge_ok = False
                    self._last_error = str(exc)
                    self._last_poll_at = poll_started_at
                    self._append_event_locked(f"브리지 조회 실패: {exc}")
                    self._queue_condition.notify_all()

            if self._stop_event.wait(self.poll_interval_seconds):
                break

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            with self._queue_condition:
                while not self._queued_jobs and not self._stop_event.is_set():
                    self._worker_status = "대기 중"
                    self._current_job_text = "-"
                    self._queue_condition.wait(timeout=0.5)
                if self._stop_event.is_set():
                    return
                job = self._queued_jobs.popleft()
                self._inflight_job_ids.add(job.id)
                self._worker_status = "처리 중"
                self._current_job_text = f"#{job.id} {job.query_text}"

            erp_template = None
            workbook_price_index: Dict[str, Dict[str, object]] = {}
            with self._lock:
                if self._erp_template:
                    erp_template = clone_erp_session(self._erp_template)
                if self._workbook_price_index:
                    workbook_price_index = dict(self._workbook_price_index)

            self._append_event(f"요청 #{job.id} 처리를 시작했습니다. 문의: {job.query_text}")
            try:
                status, result_text = build_result_text(
                    job.query_text,
                    erp_template,
                    workbook_price_index=workbook_price_index,
                )
            except Exception as exc:
                status = "FAIL"
                result_text = f"처리 중 예외가 발생했습니다.\n사유: {exc}"

            while not self._stop_event.is_set():
                try:
                    self.client.update_result(job.id, status, result_text)
                    break
                except Exception as exc:
                    with self._lock:
                        self._last_error = str(exc)
                        self._append_event_locked(f"요청 #{job.id} 결과 전송 재시도 중: {exc}")
                    if self._stop_event.wait(5.0):
                        return

            with self._queue_condition:
                self._inflight_job_ids.discard(job.id)
                self._known_job_ids.discard(job.id)
                if status == "DONE":
                    self._completed_count += 1
                    self._append_event_locked(f"요청 #{job.id} 처리가 완료되었습니다.")
                else:
                    self._failed_count += 1
                    self._append_event_locked(f"요청 #{job.id} 처리가 실패했습니다.")
                self._worker_status = "대기 중"
                self._current_job_text = "-"
                self._queue_condition.notify_all()

