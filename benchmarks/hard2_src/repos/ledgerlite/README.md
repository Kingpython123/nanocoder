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

## Payments

`Invoice.add_payment(amount)` records a (partial) payment. `outstanding` is the
total minus payments, never below zero; an invoice is *settled* when nothing is
outstanding (or when `paid` was set because it was settled elsewhere).

## Receivables aging

Invoices that are not settled are grouped by days past due: `current` (not yet due),
`1-30`, `31-60`, `61-90` and `90+`. Each range includes both ends, so an invoice
exactly 30 days past due is in `1-30`. Aging always works on the **outstanding**
amount, and settled invoices never appear in aging summaries or overdue lists.

## CSV import

`parse_csv(text, delimiter=",", decimal=".")`. German / French Excel exports use
`delimiter=";"` and `decimal=","`. Numbers (quantities and prices) may group
thousands: with `decimal="."` the separators `,`, space and no-break space are
ignored (`"1,234.50"` -> 1234.50); with `decimal=","` the separators `.`, space and
no-break space are ignored (`"1.234,50"` -> 1234.50, quantity `"1.000"` -> 1000).

## Reports

`render_report()` lists invoices in natural order of their number, case-insensitive
(`INV-2` before `INV-10`; ties keep a stable order by the raw number). Each row shows
the invoice converted to the base currency. The TOTAL line is computed the way
finance does it: sum the invoices **per currency**, convert each currency sum once,
then add those up. So the total can differ from the sum of the rounded rows.

## Running tests

    python -m pytest -q
