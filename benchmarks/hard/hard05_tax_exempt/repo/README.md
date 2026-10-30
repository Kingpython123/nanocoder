# ledgerlite

Small invoicing library: line items, taxes, discounts, multi-currency reports and
receivables aging.

## Conventions

- All money amounts are `Decimal`. Never use `float` for money.
- Amounts are rounded to cents with commercial rounding (half away from zero),
  e.g. 2.675 -> 2.68 and -2.675 -> -2.68.

## Tax rules

- Regions: DE 19 %, FR 20 %, NL 21 %.
- Category codes `food` and `books` are VAT-exempt. Codes are compared
  case-insensitively after trimming whitespace; every other code is taxed.
- Tax is computed per line on the rounded line total.

## Discounts

See [docs/DISCOUNTS.md](docs/DISCOUNTS.md).

## Receivables aging

Unpaid invoices are grouped by days past due: `current` (not yet due),
`1-30`, `31-60`, `61-90` and `90+`. Each range includes both ends, so an invoice
exactly 30 days past due is in `1-30`.

## Running tests

    python -m pytest -q
