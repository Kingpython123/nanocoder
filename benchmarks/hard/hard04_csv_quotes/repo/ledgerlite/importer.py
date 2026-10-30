"""Import invoice lines from CSV (e.g. exported from Excel or Google Sheets)."""

from __future__ import annotations

from .invoice import LineItem
from .money import to_decimal

REQUIRED_COLUMNS = ("sku", "quantity", "unit_price")


def _normalize_header(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def parse_csv(text: str) -> list[LineItem]:
    """Parse CSV text with a header row into LineItems.

    Header names are case-insensitive ("Unit Price" == "unit_price"); unknown columns
    are ignored; blank lines are skipped. Optional columns: category, description.
    """
    rows = [line.split(",") for line in text.splitlines() if line.strip()]
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
                    quantity=int(record["quantity"]),
                    unit_price=to_decimal(record["unit_price"]),
                    category=record.get("category") or "general",
                    description=record.get("description", ""),
                )
            )
        except (KeyError, ValueError) as e:
            raise ValueError(f"row {number}: {e}") from None
    return items
