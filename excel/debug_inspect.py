from __future__ import annotations

import sys

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter


def s(v: object) -> str:
    if v is None:
        return ""
    return str(v).replace("\n", " ").strip()


def main() -> None:
    # Windows 콘솔(cp949)에서 유니코드 출력 오류 방지
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    path = "test.xlsx"
    wb = load_workbook(path)
    ws = wb.worksheets[0]

    print("sheet:", ws.title)
    print("max_row:", ws.max_row, "max_col:", ws.max_column)
    print("merged_ranges_count:", len(ws.merged_cells.ranges))
    for i, rng in enumerate(list(ws.merged_cells.ranges)[:30], start=1):
        print("merged", i, str(rng))

    max_r = min(ws.max_row or 0, 200)
    max_c = min(ws.max_column or 0, 60)

    print("--- non-empty rows (top) ---")
    for r in range(1, max_r + 1):
        parts = []
        for c in range(1, max_c + 1):
            v = s(ws.cell(r, c).value)
            if v:
                parts.append(f"{get_column_letter(c)}={v}")
        if parts:
            print(f"R{r}:", " | ".join(parts))

    print("--- header candidates (contains 모델/출하/공급/할인) ---")
    keys = ["모델", "출하", "공급", "할인"]
    for r in range(1, max_r + 1):
        rowtxt = " ".join(s(ws.cell(r, c).value) for c in range(1, max_c + 1))
        if all(k in rowtxt for k in keys):
            print("candidate_row", r, ":", rowtxt)


if __name__ == "__main__":
    main()

