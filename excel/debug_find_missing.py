from __future__ import annotations

import sys
import os
import tempfile
import shutil
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter


def s(v: object) -> str:
    if v is None:
        return ""
    return str(v).replace("\n", " ").replace("\u00a0", " ").strip()


def dump_area(ws, center_row: int, *, radius: int = 8, max_col: int = 20) -> None:
    r1 = max(1, center_row - radius)
    r2 = min(ws.max_row, center_row + radius)
    for r in range(r1, r2 + 1):
        parts = []
        for c in range(1, max_col + 1):
            v = s(ws.cell(r, c).value)
            if v:
                parts.append(f"{get_column_letter(c)}={v}")
        if parts:
            print(f"R{r}:", " | ".join(parts))


def find_text_rows(ws, needle: str) -> list[int]:
    rows = []
    for r in range(1, ws.max_row + 1):
        for c in range(1, ws.max_column + 1):
            v = ws.cell(r, c).value
            if isinstance(v, str) and needle in v:
                rows.append(r)
                break
    return rows


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    src = "test.xlsx"
    if not os.path.exists(src):
        src = "test_copy.xlsx"
    fd, tmp = tempfile.mkstemp(prefix="inspect_", suffix=".xlsx")
    os.close(fd)
    shutil.copy2(src, tmp)

    wb = load_workbook(tmp)
    ws = wb.worksheets[0]

    targets = [
        "3월 PC 기획전 운영안 안내드립니다",
        "16MR70.ASDK",
        "3월 에어컨 기획전 운영안 안내드립니다",
        "SET모델명",
        "출하가 (설치비제외)",
        "공급가 (설치비제외)",
    ]

    for t in targets:
        rows = find_text_rows(ws, t)
        print("\n===", t, "rows:", rows[:20], "count:", len(rows))
        for rr in rows[:3]:
            print(f"-- dump around row {rr} --")
            dump_area(ws, rr, radius=10, max_col=min(ws.max_column, 20))


if __name__ == "__main__":
    main()

