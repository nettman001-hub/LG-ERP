from __future__ import annotations

import os
import shutil
import sys
import tempfile

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from excel_price_tables import _cell_value as cell_value  # type: ignore


def s(v: object) -> str:
    if v is None:
        return ""
    return str(v).replace("\n", " ").replace("\u00a0", " ").strip()


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    fd, tmp = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    shutil.copy2("test.xlsx", tmp)

    ws = load_workbook(tmp).worksheets[0]
    max_col = min(ws.max_column, 20)

    for r in range(248, 256):
        parts = []
        for c in range(1, max_col + 1):
            v = cell_value(ws, r, c)
            if v is None:
                continue
            vv = s(v)
            if vv:
                parts.append(f"{get_column_letter(c)}={vv}")
        if parts:
            print(f"R{r}:", " | ".join(parts))

    print("\n--- raw grid (R252-253, C1-12) incl merged representative ---")
    for r in (252, 253):
        row = []
        for c in range(1, 13):
            row.append(f"{get_column_letter(c)}:{s(cell_value(ws, r, c)) or '-'}")
        print(f"R{r}:", "  ".join(row))


if __name__ == "__main__":
    main()

