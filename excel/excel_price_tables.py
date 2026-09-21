from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import math
import re

from openpyxl.worksheet.worksheet import Worksheet


_CANONICAL_KEYS = ("model", "msrp", "supply", "discount")

# 헤더 표기는 파일마다 달라서 동의어를 폭넓게 허용합니다.
# normalize 이후 비교(공백/기호 제거, 소문자화) 기준입니다.
_HEADER_SYNONYMS: Dict[str, set[str]] = {
    "model": {"모델명", "모델"},
    "msrp": {"출하가"},
    "supply": {"공급가", "단가"},
    "discount": {"할인율", "dc율", "d/c율", "d/c", "dc", "d/c율(%)", "dc율(%)"},
}


@dataclass(frozen=True)
class TableRegion:
    index: int
    name: str
    header_row: int
    first_data_row: int
    last_data_row: int
    col_model: int
    col_msrp: int  # 출하가
    col_supply: int  # 공급가
    col_discount: int  # 할인율

    @property
    def n_rows(self) -> int:
        return max(0, self.last_data_row - self.first_data_row + 1)


def _normalize_header(value: object) -> str:
    if value is None:
        return ""
    s = str(value).replace("\u00a0", " ").strip().lower()
    # 흔한 표기 변형(d/c, dc, %, 괄호 등)을 최대한 정규화
    s = s.replace("d/c", "dc")
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[()\[\]{}<>:%.,·\-/\\\\|_]+", "", s)
    return s


def _is_effectively_empty_row(ws: Worksheet, row: int, max_col: int) -> bool:
    for c in range(1, max_col + 1):
        v = _cell_value(ws, row, c)
        if v is None:
            continue
        if isinstance(v, str) and v.strip() == "":
            continue
        return False
    return True


def _cell_value(ws: Worksheet, row: int, col: int) -> object:
    """
    병합셀의 경우, 병합 영역 내 셀 값은 None일 수 있으므로
    해당 병합영역의 좌상단 값을 대표값으로 사용합니다.
    """
    cell = ws.cell(row=row, column=col)
    if cell.value is not None:
        return cell.value
    for rng in ws.merged_cells.ranges:
        if rng.min_row <= row <= rng.max_row and rng.min_col <= col <= rng.max_col:
            return ws.cell(row=rng.min_row, column=rng.min_col).value
    return None


def _matches_header(token: str, key: str) -> bool:
    """
    헤더 표기 변형을 위해 부분일치까지 허용합니다.
    예: 'set모델명' -> '모델명' 포함으로 model로 매칭
        'dc' -> discount로 매칭
    """
    for syn in _HEADER_SYNONYMS[key]:
        if token == syn:
            return True
        if syn and syn in token:
            return True
        if token and token in syn:
            return True
    return False


def _find_header_map(
    ws: Worksheet, start_row: int, max_col: int, *, header_rows: int
) -> Optional[Dict[str, int]]:
    """
    start_row부터 header_rows 만큼(1~3) 훑어서, 필요한 헤더 컬럼을 찾습니다.
    (다중 행 헤더 지원)
    """
    header_map: Dict[str, int] = {}
    for rr in range(start_row, start_row + header_rows):
        for c in range(1, max_col + 1):
            token = _normalize_header(_cell_value(ws, rr, c))
            if not token:
                continue
            for key in _CANONICAL_KEYS:
                if key in header_map:
                    continue
                if _matches_header(token, key):
                    header_map[key] = c
    if all(k in header_map for k in _CANONICAL_KEYS):
        return header_map
    return None


def _find_partial_header_map(ws: Worksheet, start_row: int, max_col: int, *, header_rows: int) -> Dict[str, int]:
    header_map: Dict[str, int] = {}
    for rr in range(start_row, start_row + header_rows):
        for c in range(1, max_col + 1):
            token = _normalize_header(_cell_value(ws, rr, c))
            if not token:
                continue
            for key in _CANONICAL_KEYS:
                if key in header_map:
                    continue
                if _matches_header(token, key):
                    header_map[key] = c
    return header_map


_MODEL_LIKE_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9][A-Za-z0-9-]*\\.[A-Za-z0-9./-]+$")


def _infer_model_col_from_data(
    ws: Worksheet,
    first_data_row: int,
    *,
    max_row: int,
    max_col: int,
    exclude_cols: set[int],
    scan_rows: int = 30,
) -> Optional[int]:
    """
    헤더에 모델명이 없는 경우(예: '구분'만 있는 경우) 데이터 패턴으로 모델 컬럼을 추정합니다.
    - 점(.)이 포함되고 영문+숫자가 섞인 토큰을 높은 점수로 평가
    """
    r2 = min(max_row, first_data_row + scan_rows - 1)
    best_col = None
    best_score = 0
    for c in range(1, max_col + 1):
        if c in exclude_cols:
            continue
        score = 0
        for r in range(first_data_row, r2 + 1):
            v = ws.cell(row=r, column=c).value
            if not isinstance(v, str):
                continue
            t = v.strip()
            if not t:
                continue
            if _MODEL_LIKE_RE.match(t):
                score += 3
            elif "." in t and any(ch.isalpha() for ch in t) and any(ch.isdigit() for ch in t):
                score += 2
        if score > best_score:
            best_score = score
            best_col = c
    if best_score >= 4:
        return best_col
    return None


def detect_price_tables(ws: Worksheet, *, scan_rows: int = 2000) -> List[TableRegion]:
    """
    첫 번째 시트에서 '가격표 테이블' 블록들을 자동 감지합니다.

    감지 규칙(기본):
    - 어떤 행부터 1~3줄 범위 안에서 (모델명/출하가/공급가(or 단가)/할인율(or DC율))이
      모두 발견되면 그 블록을 헤더로 간주
    - 헤더 아래로 빈 행이 나오기 전까지를 데이터 범위로 간주
    """
    max_row = min(ws.max_row or 0, scan_rows)
    max_col = ws.max_column or 0
    if max_row <= 0 or max_col <= 0:
        return []

    tables: List[TableRegion] = []
    r = 1
    while r <= max_row:
        header_map = None
        header_rows_used = 0
        for rows_used in (1, 2, 3):
            if r + rows_used - 1 > max_row:
                continue
            header_map = _find_header_map(ws, r, max_col, header_rows=rows_used)
            if header_map:
                header_rows_used = rows_used
                break
        if not header_map:
            # 모델명 헤더가 없는 특수 케이스(PC 테이블 등)를 위해 부분 매칭 후 보정
            for rows_used in (1, 2, 3):
                if r + rows_used - 1 > max_row:
                    continue
                partial = _find_partial_header_map(ws, r, max_col, header_rows=rows_used)
                if {"msrp", "supply", "discount"}.issubset(partial.keys()) and "model" not in partial:
                    first_data = r + rows_used
                    inferred_model = _infer_model_col_from_data(
                        ws,
                        first_data,
                        max_row=max_row,
                        max_col=max_col,
                        exclude_cols={partial["msrp"], partial["supply"], partial["discount"]},
                    )
                    if inferred_model is not None:
                        partial["model"] = inferred_model
                        header_map = partial
                        header_rows_used = rows_used
                        break
            if not header_map:
                r += 1
                continue

        first_data = r + header_rows_used
        last_data = first_data - 1
        rr = first_data
        while rr <= max_row and not _is_effectively_empty_row(ws, rr, max_col):
            # 출하가/공급가/할인율(DC율)이 모두 비면 테이블 종료일 수 있음 (섹션 제목/주석 행 분리)
            if (
                ws.cell(row=rr, column=header_map["msrp"]).value is None
                and ws.cell(row=rr, column=header_map["supply"]).value is None
                and ws.cell(row=rr, column=header_map["discount"]).value is None
            ):
                # 바로 다음 행들에 데이터가 이어지는 경우('비고' 등 부분 참조)가 있으므로 Look-ahead 검증
                is_end_of_table = True
                for look_r in range(rr + 1, min(rr + 10, max_row + 1)):
                    if _is_effectively_empty_row(ws, look_r, max_col):
                        break # 진짜 빈 행이면 테이블 끝 맞음
                    
                    # 새로운 헤더가 등장하면 테이블 끝 맞음
                    temp_map = _find_partial_header_map(ws, look_r, max_col, header_rows=1)
                    if "model" in temp_map and ("msrp" in temp_map or "supply" in temp_map):
                        break
                        
                    # 이어지는 데이터가 있으면 중간 빈 행(주석/비고)일 뿐임
                    look_msrp = _to_number(ws.cell(row=look_r, column=header_map["msrp"]).value)
                    look_supply = _to_number(ws.cell(row=look_r, column=header_map["supply"]).value)
                    if look_msrp is not None or look_supply is not None:
                        is_end_of_table = False
                        break
                
                if is_end_of_table:
                    break
            last_data = rr
            rr += 1

        # 데이터가 1행도 없으면 테이블로 취급하지 않음
        if last_data >= first_data:
            section_name = infer_section_name(ws, r, max_col=max_col)
            tables.append(
                TableRegion(
                    index=len(tables) + 1,
                    name=section_name,
                    header_row=r,
                    first_data_row=first_data,
                    last_data_row=last_data,
                    col_model=header_map["model"],
                    col_msrp=header_map["msrp"],
                    col_supply=header_map["supply"],
                    col_discount=header_map["discount"],
                )
            )

        r = rr + 1  # 다음 블록으로 점프(빈 행 다음부터)

    return tables


def _to_number(value: object) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip().replace(",", "")
        if s == "":
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _discount_to_ratio(discount_value: object) -> Optional[float]:
    """
    엑셀 셀의 할인율 표기를 0~1 비율로 변환.
    - 0.2 / 20% / 20 / "20" / "20%" 등을 허용
    """
    v = _to_number(discount_value)
    if v is None:
        if isinstance(discount_value, str) and "%" in discount_value:
            num = discount_value.replace("%", "").strip()
            v = _to_number(num)
        else:
            return None
    if v is None:
        return None
    if v > 1.0:
        return v / 100.0
    if v < 0:
        return None
    return v


def recalc_supply_price(msrp: float, discount_ratio: float) -> int:
    """
    공급가 = 출하가 * (1 - 할인율), 10원 단위 버림.
    """
    raw = msrp * (1.0 - discount_ratio)
    return int(math.floor(raw / 100.0) * 100)


def clamp_discount_ratio(ratio: float) -> float:
    if ratio < 0.0:
        return 0.0
    if ratio > 1.0:
        return 1.0
    return ratio


def parse_discount_ratio(value: object) -> Optional[float]:
    return _discount_to_ratio(value)


def apply_discount_to_table(
    ws: Worksheet, table: TableRegion, new_discount_ratio: float, *, write_discount_cell: bool = True
) -> Tuple[int, int]:
    """
    테이블 내 모든 행에 동일한 할인율을 적용하고 공급가를 갱신합니다.
    반환: (업데이트된 행 수, 스킵된 행 수)
    """
    updated = 0
    skipped = 0
    for r in range(table.first_data_row, table.last_data_row + 1):
        msrp_val = _to_number(ws.cell(row=r, column=table.col_msrp).value)
        model_val = ws.cell(row=r, column=table.col_model).value

        # 모델명도 없고 출하가도 없으면 데이터 행이 아닐 가능성이 큼 -> 스킵
        if (model_val is None or (isinstance(model_val, str) and model_val.strip() == "")) and msrp_val is None:
            skipped += 1
            continue

        if msrp_val is None:
            skipped += 1
            continue

        new_supply = recalc_supply_price(msrp_val, new_discount_ratio)
        ws.cell(row=r, column=table.col_supply).value = new_supply
        if write_discount_cell:
            ws.cell(row=r, column=table.col_discount).value = new_discount_ratio
        updated += 1

    return updated, skipped


def apply_discount_delta_to_table(
    ws: Worksheet,
    table: TableRegion,
    delta_percent_point: float,
    *,
    write_discount_cell: bool = True,
) -> Tuple[int, int]:
    """
    테이블별 "조정값"(%p)을 받아 각 행의 기존 할인율(DC율)에 가감한 뒤 공급가를 갱신합니다.
    - 예: 기존 0.25(=25%) + delta +2.0%p => 0.27
    - 할인율은 0~1로 clamp
    """
    updated = 0
    skipped = 0
    delta_ratio = delta_percent_point / 100.0

    for r in range(table.first_data_row, table.last_data_row + 1):
        msrp_val = _to_number(ws.cell(row=r, column=table.col_msrp).value)
        model_val = ws.cell(row=r, column=table.col_model).value

        if (model_val is None or (isinstance(model_val, str) and model_val.strip() == "")) and msrp_val is None:
            skipped += 1
            continue
        if msrp_val is None:
            skipped += 1
            continue

        old_ratio = _discount_to_ratio(ws.cell(row=r, column=table.col_discount).value)
        if old_ratio is None:
            old_ratio = 0.0

        new_ratio = clamp_discount_ratio(old_ratio + delta_ratio)
        new_supply = recalc_supply_price(msrp_val, new_ratio)

        ws.cell(row=r, column=table.col_supply).value = new_supply
        if write_discount_cell:
            ws.cell(row=r, column=table.col_discount).value = new_ratio
        updated += 1

    return updated, skipped


def apply_discount_delta_to_row(
    ws: Worksheet,
    table: TableRegion,
    row: int,
    delta_percent_point: float,
    *,
    write_discount_cell: bool = True,
) -> bool:
    """
    특정 단일 행에 대해서만 할인율(DC율) 조정값을 적용하고 공급가를 갱신합니다.
    (연관 모델 일괄 수정용)
    """
    msrp_val = _to_number(ws.cell(row=row, column=table.col_msrp).value)
    if msrp_val is None:
        return False

    delta_ratio = delta_percent_point / 100.0
    old_ratio = _discount_to_ratio(ws.cell(row=row, column=table.col_discount).value)
    if old_ratio is None:
        old_ratio = 0.0

    new_ratio = clamp_discount_ratio(old_ratio + delta_ratio)
    new_supply = recalc_supply_price(msrp_val, new_ratio)

    ws.cell(row=row, column=table.col_supply).value = new_supply
    if write_discount_cell:
        ws.cell(row=row, column=table.col_discount).value = new_ratio
    return True


def infer_table_discount(ws: Worksheet, table: TableRegion) -> Optional[float]:
    """
    테이블의 '대표 할인율'을 추정합니다.
    - 첫 데이터 행의 할인율을 우선 사용
    - 없으면 다음 행들에서 첫 번째로 파싱 가능한 할인율을 사용
    """
    for r in range(table.first_data_row, table.last_data_row + 1):
        v = ws.cell(row=r, column=table.col_discount).value
        ratio = _discount_to_ratio(v)
        if ratio is not None:
            return ratio
    return None


def infer_section_name(ws: Worksheet, header_row: int, *, max_col: int) -> str:
    """
    헤더 위쪽에서 섹션명을 휴리스틱으로 추정합니다.
    - header_row 위로 최대 20행을 역방향으로 훑고,
    - 가장 가까운 '짧은 제목성' 텍스트를 선택합니다.
    """
    def clean_title(t: str) -> str:
        t = t.replace("\u00a0", " ").strip()
        t = re.sub(r"\s+", " ", t)
        return t

    blacklist_fragments = ("운영기간", "단위", "vat", "vat포함", "원,", "원)", "%")
    bad_prefix = ("-", "※", "*", "(", "[")

    candidates: list[tuple[int, int, str]] = []  # (score, distance, title)

    for rr in range(header_row - 1, max(1, header_row - 20), -1):
        distance = header_row - rr
        cols = [2, 1, 3, 4, 5, 6]
        for cc in [c for c in cols if c <= max_col]:
            v = ws.cell(row=rr, column=cc).value
            if not isinstance(v, str):
                continue
            t = clean_title(v)
            if not t:
                continue
            if t.startswith(bad_prefix):
                continue
            low = t.lower()
            if any(frag in low for frag in blacklist_fragments):
                continue
            if len(t) > 90:
                continue

            score = 0
            if "안내드립니다" in t:
                score += 10
            if "기획전" in t:
                score += 3
            if t.strip().startswith("3월") or t.strip().startswith("4월") or t.strip().startswith("2월"):
                score += 2
            # 짧을수록 제목일 가능성
            score += max(0, 6 - (len(t) // 15))
            # 가까울수록 가산
            score += max(0, 6 - distance)

            candidates.append((score, distance, t))

    if candidates:
        candidates.sort(key=lambda x: (-x[0], x[1], len(x[2])))
        best = candidates[0][2]
        if len(best) <= 60:
            return best
        return best[:60].rstrip() + "…"

    return f"테이블 {header_row}"

