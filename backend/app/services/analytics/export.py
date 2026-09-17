"""CSV/Excel export for any analytics table (plan.md Phase 7): finance and
operations staff need raw exports, not just the JSON the dashboard consumes.
Both formats are built from the same flat list-of-dicts a rollup type
already produces, so there is exactly one code path per format regardless
of which metric is being exported.
"""

import csv
import io

from openpyxl import Workbook


def rows_to_csv(rows: list[dict]) -> str:
    if not rows:
        return ""
    fieldnames = list(rows[0].keys())
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def rows_to_xlsx(rows: list[dict]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "export"

    if rows:
        fieldnames = list(rows[0].keys())
        sheet.append(fieldnames)
        for row in rows:
            sheet.append([row.get(field) for field in fieldnames])

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
