from __future__ import annotations

import sys

from openpyxl import load_workbook

from excel_price_tables import detect_price_tables, infer_table_discount


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    # Excel에서 원본을 열어 잠기는 경우가 있어 복사본을 사용
    wb = load_workbook("test_copy.xlsx")
    ws = wb.worksheets[0]
    tables = detect_price_tables(ws)
    print("tables_found:", len(tables))
    for t in tables:
        disc = infer_table_discount(ws, t)
        print(
            f"- idx={t.index} header_row={t.header_row} data={t.first_data_row}~{t.last_data_row} "
            f"cols(model/msrp/supply/discount)=({t.col_model},{t.col_msrp},{t.col_supply},{t.col_discount}) "
            f"discount_inferred={disc}"
        )


if __name__ == "__main__":
    main()

