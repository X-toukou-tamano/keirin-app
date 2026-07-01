import re
import unicodedata
from calendar import monthrange
from datetime import date

from openpyxl import load_workbook


TARGET_BLOCK = "玉野"


def clean(text):
    if text is None:
        return ""
    return (
        unicodedata.normalize("NFKC", str(text))
        .replace("　", "")
        .replace(" ", "")
        .strip()
    )


def build_merged_map(ws):
    merged = {}
    for rng in ws.merged_cells.ranges:
        min_col, min_row, max_col, max_row = rng.bounds
        value = ws.cell(min_row, min_col).value
        for r in range(min_row, max_row + 1):
            for c in range(min_col, max_col + 1):
                merged[(r, c)] = value
    return merged


def merged_value(cell, merged_map):
    return cell.value if cell.value is not None else merged_map.get((cell.row, cell.column))


def resolve_year(filename, month):
    m = re.search(r"R([0-9０-９]+)", filename)
    if m:
        fiscal = 2018 + int(
            m.group(1).translate(str.maketrans("０１２３４５６７８９", "0123456789"))
        )
    else:
        m = re.search(r"(20\d{2})", filename)
        fiscal = int(m.group(1))

    return fiscal if month >= 4 else fiscal + 1


def find_months(ws, merged_map):
    result = {}

    for row in ws.iter_rows():
        for cell in row:
            value = clean(merged_value(cell, merged_map))

            m = re.match(r"^([1-9]|1[0-2])月$", value)
            if m:
                month = int(m.group(1))
                if month not in result:
                    result[month] = cell

    return result


def get_day1_column(ws, month_cell):
    for rng in ws.merged_cells.ranges:
        if month_cell.coordinate in rng:
            return rng.max_col + 1
    return month_cell.column + 1


def find_block_column(ws, merged_map):
    for row in range(1, 100):
        for col in range(1, 10):
            value = clean(merged_value(ws.cell(row, col), merged_map))
            if value == TARGET_BLOCK:
                return col
    return 2


def get_organizer(excel_path, target_date):
    wb = load_workbook(excel_path, data_only=True)
    filename = excel_path.split("/")[-1]

    organizer = "玉野"

    try:
        for ws in wb.worksheets:

            if ws.sheet_state != "visible":
                continue

            merged_map = build_merged_map(ws)
            months = find_months(ws, merged_map)

            if target_date.month not in months:
                continue

            month_cell = months[target_date.month]

            if resolve_year(filename, target_date.month) != target_date.year:
                continue

            day1_col = get_day1_column(ws, month_cell)
            target_col = day1_col + target_date.day - 1

            block_col = find_block_column(ws, merged_map)

            start_row = month_cell.row
            end_row = ws.max_row

            for row in range(start_row, end_row + 1):

                block = clean(merged_value(ws.cell(row, block_col), merged_map))

                if block != TARGET_BLOCK:
                    continue

                value = clean(merged_value(ws.cell(row, target_col), merged_map))

                if not value:
                    continue

                m = re.match(r"(.+?)in玉野", value)

                if m:
                    organizer = m.group(1)
                    break

                if value == "玉野":
                    organizer = "玉野"
                    break

            break

    finally:
        wb.close()

    return organizer
