from __future__ import annotations

import csv

from PySide6.QtWidgets import QTableWidget


def table_rows_for_csv(table: QTableWidget) -> list[list[str]]:
    headers = [
        table.horizontalHeaderItem(col).text() if table.horizontalHeaderItem(col) else ""
        for col in range(table.columnCount())
    ]
    rows: list[list[str]] = [headers]
    for row in range(table.rowCount()):
        values: list[str] = []
        for col in range(table.columnCount()):
            cell = table.item(row, col)
            values.append(cell.text() if cell is not None else "")
        rows.append(values)
    return rows


def write_csv_file(path: str, rows: list[list[str]], encoding: str = "utf-8-sig") -> None:
    with open(path, "w", newline="", encoding=encoding) as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)
