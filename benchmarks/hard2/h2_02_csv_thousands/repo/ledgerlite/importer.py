"""Import invoice lines from CSV (e.g. exported from Excel or Google Sheets)."""

from __future__ import annotations

import csv
import io

from .invoice import LineItem
from .money import to_decimal

REQUIRED_COLUMNS = ("sku", "quantity", "unit_price")
# characters that may group thousands, per decimal separator (see README, "CSV import")
THOUSANDS_SEPARATORS = {".": (",", " ", " "), ",": (".", " ", " ")}


def _normalize_header(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def _normalize_number(text: str, decimal: str) -> str:
    """'1.234,56' (decimal=',') or '1,234.56' (decimal='.') -> '1234.56'."""
    s = text.strip()
    if decimal == ",":
        s = s.replace(",", ".")
    return s


def parse_csv(text: str, delimiter: str = ",", decimal: str = ".") -> list[LineItem]:
    """Parse CSV text with a header row into LineItems.

    Header names are case-insensitive ("Unit Price" == "unit_price"); unknown columns
    are ignored; blank lines are skipped. Optional columns: category, description.
    `delimiter` separates fields, `decimal` is the decimal separator used in numbers.
    """
    if decimal not in THOUSANDS_SEPARATORS:
        raise ValueError(f"unsupported decimal separator {decimal!r}")
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [row for row in reader if row and any(cell.strip() for cell in row)]
    if not rows:
        return []
    header = [_normalize_header(h) for h in rows[0]]
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise ValueError(f"missing column(s): {', '.join(missing)}")
    items = []
    for number, row in enumerate(rows[1:], start=2):
        record = dict(zip(header, (cell.strip() for cell in row)))
        try:
            items.append(
                LineItem(
                    sku=record["sku"],
                    quantity=int(_normalize_number(record["quantity"], decimal)),
                    unit_price=to_decimal(_normalize_number(record["unit_price"], decimal)),
                    category=record.get("category") or "general",
                    description=record.get("description", ""),
                )
            )
        except (KeyError, ValueError) as e:
            raise ValueError(f"row {number}: {e}") from None
    return items
