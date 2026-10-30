r"""hard2 任务集（v2）。格式同 hard_src/specs.py，由 `python benchmarks/build_hard.py --suite hard2` 生成。

v1 的结论是：bug 在单个函数里、issue 一指就中的题，模型几乎全对；真正拉开差距的是
"修法看起来对，但违反了仓库文档里的约束"。所以 v2 的每道题至少满足下面一条：
- 规则写在 README / docstring 里，issue 只描述一个现象（隐含约束）
- 一个 issue 背后有两处相关的问题，只修一处不够（多处修改）
- 症状出现在上层，根因在下层的共用函数里；只在上层打补丁，其他调用方仍然是坏的（根因定位）
- 需要补全一个有很多边界情况的功能（边界情况多）
"""

TASKS = [
    # ---------------------------------------------------------------- ledgerlite
    {
        "id": "h2_01_float_amounts",
        "repo": "ledgerlite",
        "category": "root_cause",
        "issue": (
            "Our POS integration sends prices as Python floats. `inv.add_line('A', 1, 1.005)` gives a "
            "line total of 1.00, but `inv.add_line('A', 1, '1.005')` gives 1.01. A float should behave "
            "exactly like the number it prints as, wherever we pass amounts into ledgerlite."
        ),
        "mutations": [
            (
                "ledgerlite/money.py",
                '"""Money helpers. All amounts are Decimal; floats are converted via their repr."""',
                '"""Money helpers. All amounts are Decimal."""',
            ),
            ("ledgerlite/money.py", "        return Decimal(repr(value))\n", "        return Decimal(value)\n"),
        ],
        "f2p": ["test_to_decimal_float", "test_add_line_float", "test_line_item_float", "test_discount_float", "test_rates_float"],
    },
    {
        "id": "h2_02_csv_thousands",
        "repo": "ledgerlite",
        "category": "edge_cases",
        "issue": (
            "Importing a German Excel export with `parse_csv(text, delimiter=';', decimal=',')` fails:\n\n"
            "    ValueError: row 3: not a valid amount: '1.234.56'\n\n"
            "The cell says `1.234,56`. Prices below 1000 such as `0,99` import fine."
        ),
        "mutations": [
            (
                "ledgerlite/importer.py",
                '    s = text.strip()\n    for sep in THOUSANDS_SEPARATORS[decimal]:\n        s = s.replace(sep, "")\n',
                "    s = text.strip()\n",
            ),
        ],
        "f2p": ["test_german_thousands", "test_negative_german", "test_space_grouping", "test_english_grouping"],
    },
    {
        "id": "h2_03_report_natural_order",
        "repo": "ledgerlite",
        "category": "spec",
        "issue": "The receivables report lists INV-10 and INV-11 before INV-9.",
        "mutations": [
            ("ledgerlite/report.py", "import re\nfrom collections", "from collections"),
            (
                "ledgerlite/report.py",
                r'''def _natural_key(number: str) -> tuple:
    parts = re.split(r"(\d+)", number.casefold())
    return ([int(p) if p.isdigit() else p for p in parts], number)


''',
                "",
            ),
            ("ledgerlite/report.py", "key=lambda i: _natural_key(i.number)", "key=lambda i: i.number"),
        ],
        "f2p": ["test_numbers_sort_naturally", "test_case_insensitive", "test_multiple_number_groups", "test_render_order"],
    },
    {
        "id": "h2_04_report_total",
        "repo": "ledgerlite",
        "category": "spec",
        "issue": (
            "The TOTAL line of our EUR receivables report doesn't match what finance computes. "
            "Example: three USD invoices of 0.05 each with EUR/USD at 1.10. The report says "
            "TOTAL 0.15 EUR, finance says 0.14 EUR."
        ),
        "mutations": [
            ("ledgerlite/report.py", "from collections import defaultdict\n", ""),
            (
                "ledgerlite/report.py",
                r'''    sums: defaultdict[str, Decimal] = defaultdict(lambda: ZERO)
    for inv in invoices:
        sums[inv.currency.upper()] += inv.total
    return sum((converter.convert(amount, cur, base_currency) for cur, amount in sorted(sums.items())), ZERO)
''',
                r'''    return sum((converter.convert(inv.total, inv.currency, base_currency) for inv in invoices), ZERO)
''',
            ),
        ],
        "f2p": ["test_total_per_currency", "test_mixed_currencies_total", "test_render_total_line"],
    },
    {
        "id": "h2_05_aging_payments",
        "repo": "ledgerlite",
        "category": "multi_location",
        "issue": (
            "Since we started recording partial payments with add_payment(), the aging numbers are off: "
            "a 100.00 invoice with 40.00 paid still counts as 100.00, and invoices that customers paid "
            "off completely still show up as overdue."
        ),
        "mutations": [
            ("ledgerlite/aging.py", "    if invoice.is_settled or invoice.due is None:\n", "    if invoice.paid or invoice.due is None:\n"),
            (
                "ledgerlite/aging.py",
                '    """Outstanding amount per aging bucket (settled invoices are left out)."""',
                '    """Total amount due per aging bucket (unpaid invoices only)."""',
            ),
            (
                "ledgerlite/aging.py",
                "        if inv.is_settled:\n            continue\n        totals[bucket_for(days_overdue(inv, today))] += inv.outstanding\n",
                "        if inv.paid:\n            continue\n        totals[bucket_for(days_overdue(inv, today))] += inv.total\n",
            ),
        ],
        "f2p": [
            "test_partial_payment_in_summary",
            "test_fully_paid_by_payments_excluded",
            "test_overpaid_invoice_excluded",
            "test_empty_invoice_not_overdue",
        ],
    },
    # ---------------------------------------------------------------- flowkit
    {
        "id": "h2_06_cron_day_or",
        "repo": "flowkit",
        "category": "spec",
        "issue": (
            "`CronSpec('0 9 1 * 1')` should fire on the 1st of every month and on every Monday, "
            "like crontab does. Right now it only fires when the 1st happens to be a Monday."
        ),
        "mutations": [
            (
                "flowkit/cron.py",
                r'''        self.weekdays = frozenset(0 if d == 7 else d for d in weekdays)
        # see README: a day field is "restricted" unless it starts with '*'
        self.day_restricted = not parts[2].startswith("*")
        self.weekday_restricted = not parts[4].startswith("*")

    def matches(self, dt: datetime) -> bool:
        if not (dt.minute in self.minutes and dt.hour in self.hours and dt.month in self.months):
            return False
        day_ok = dt.day in self.days
        weekday_ok = dt.isoweekday() % 7 in self.weekdays
        if self.day_restricted and self.weekday_restricted:
            return day_ok or weekday_ok
        return day_ok and weekday_ok
''',
                r'''        self.weekdays = frozenset(0 if d == 7 else d for d in weekdays)

    def matches(self, dt: datetime) -> bool:
        return (
            dt.minute in self.minutes
            and dt.hour in self.hours
            and dt.day in self.days
            and dt.month in self.months
            and dt.isoweekday() % 7 in self.weekdays
        )
''',
            ),
        ],
        "f2p": ["test_both_restricted_is_or", "test_next_after_or", "test_lists_ranges_or"],
    },
    {
        "id": "h2_07_template_quotes",
        "repo": "flowkit",
        "category": "edge_cases",
        "issue": (
            "`{{ status | default('n/a | unknown') }}` raises `TemplateError: bad filter syntax`. "
            "And `{{ x | default('}}') }}` renders garbage."
        ),
        "mutations": [
            (
                "flowkit/template.py",
                "from typing import Any, Callable, Iterator, Mapping\n\n_FILTER",
                "from typing import Any, Callable, Mapping\n\n" + r'_EXPR = re.compile(r"\{\{\s*(.*?)\s*\}\}")' + "\n_FILTER",
            ),
            (
                "flowkit/template.py",
                r'''def _split_pipes(expr: str) -> list[str]:
    """Split on '|' that are not inside a quoted string."""
    parts, buf, quote, i = [], [], None, 0
    while i < len(expr):
        ch = expr[i]
        if quote:
            buf.append(ch)
            if ch == "\\" and i + 1 < len(expr):
                buf.append(expr[i + 1])
                i += 1
            elif ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
            buf.append(ch)
        elif ch == "|":
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    if quote:
        raise TemplateError(f"unterminated string in {expr!r}")
    parts.append("".join(buf).strip())
    return parts


def _expressions(template: str) -> Iterator[tuple[int, int, str]]:
    """Yield (start, end, inner text) for each {{ ... }}; '}}' inside quotes does not close it."""
    pos = 0
    while (start := template.find("{{", pos)) != -1:
        i, quote = start + 2, None
        while i < len(template):
            ch = template[i]
            if quote:
                if ch == "\\":
                    i += 1
                elif ch == quote:
                    quote = None
            elif ch in "'\"":
                quote = ch
            elif template.startswith("}}", i):
                break
            i += 1
        else:
            raise TemplateError(f"unclosed '{{{{' at position {start}")
        yield start, i + 2, template[start + 2 : i]
        pos = i + 2


def render(template: str, context: Mapping[str, Any]) -> str:
    """Filters are applied left to right. Filter arguments are Python literals; quoted
    strings may contain '|' and '}}'."""
    out, pos = [], 0
    for start, end, inner in _expressions(template):
        path, *filters = _split_pipes(inner.strip())
        value = _lookup(context, path)
        for f in filters:
            name, args = _parse_filter(f)
            value = FILTERS[name](value, *args)
        out.append(template[pos:start])
        out.append("" if value is None else str(value))
        pos = end
    out.append(template[pos:])
    return "".join(out)
''',
                r'''def render(template: str, context: Mapping[str, Any]) -> str:
    """Filters are applied left to right. Filter arguments are Python literals; quoted
    strings may contain '|' and '}}'."""

    def substitute(m: re.Match) -> str:
        path, *filters = (part.strip() for part in m.group(1).split("|"))
        value = _lookup(context, path)
        for f in filters:
            name, args = _parse_filter(f)
            value = FILTERS[name](value, *args)
        return "" if value is None else str(value)

    return _EXPR.sub(substitute, template)
''',
            ),
        ],
        "f2p": [
            "test_pipe_inside_single_quotes",
            "test_pipe_inside_double_quotes",
            "test_closing_braces_inside_quotes",
            "test_escaped_quote_in_arg",
        ],
    },
    {
        "id": "h2_08_events_errors",
        "repo": "flowkit",
        "category": "spec",
        "issue": (
            "If one event handler raises, the remaining handlers for that event never run. "
            "One misbehaving plugin breaks all the others."
        ),
        "mutations": [
            (
                "flowkit/events.py",
                r'''        handlers = list(self._handlers.get(event, ()))
        first_error: Exception | None = None
        for h in handlers:
            try:
                h(payload)
            except Exception as e:
                if first_error is None:
                    first_error = e
        if first_error is not None:
            raise first_error
        return len(handlers)
''',
                r'''        handlers = list(self._handlers.get(event, ()))
        for h in handlers:
            h(payload)
        return len(handlers)
''',
            ),
        ],
        "f2p": ["test_remaining_handlers_run", "test_all_handlers_run_with_several_errors"],
    },
    {
        "id": "h2_09_cache_expired_first",
        "repo": "flowkit",
        "category": "multi_location",
        "issue": (
            "With ttl set, a full LRUCache evicted an entry I had set a few seconds earlier, while "
            "several long-expired entries were still sitting in it."
        ),
        "mutations": [
            (
                "flowkit/cache.py",
                r'''    def _purge_expired(self) -> None:
        if self.ttl is None:
            return
        now = self._clock()
        for key in [k for k, entry in self._data.items() if self._expired(entry, now)]:
            del self._data[key]

''',
                "",
            ),
            ("flowkit/cache.py", "        if len(self._data) > self.capacity:\n            self._purge_expired()\n", ""),
            ("flowkit/cache.py", "        self._purge_expired()\n        return len(self._data)\n", "        return len(self._data)\n"),
            ("flowkit/cache.py", "        self._purge_expired()\n        return list(self._data)\n", "        return list(self._data)\n"),
        ],
        "f2p": ["test_expired_dropped_before_live", "test_len_counts_live_only", "test_keys_live_only"],
    },
    {
        "id": "h2_10_pipeline_only",
        "repo": "flowkit",
        "category": "logic",
        "issue": (
            "`pipeline.run(only=['report'])` fails with `KeyError: 'fetch'`. "
            "report depends on load, and load depends on fetch."
        ),
        "mutations": [
            (
                "flowkit/pipeline.py",
                r'''        needed: set[str] = set()
        stack = list(names)
        while stack:
            name = stack.pop()
            if name not in self.steps:
                raise ValueError(f"unknown step {name!r}")
            if name in needed:
                continue
            needed.add(name)
            stack.extend(self.steps[name].depends_on)
        return needed
''',
                r'''        needed: set[str] = set()
        for name in names:
            if name not in self.steps:
                raise ValueError(f"unknown step {name!r}")
            needed.add(name)
            needed.update(self.steps[name].depends_on)
        return needed
''',
            ),
        ],
        "f2p": ["test_only_runs_transitive_deps", "test_only_multiple_targets_shared_deps", "test_only_with_diamond"],
    },
    {
        "id": "h2_11_env_config",
        "repo": "flowkit",
        "category": "multi_location",
        "issue": (
            "We deploy with FLOWKIT_RETRY__MAX_RETRIES=5 in the environment and pass "
            "environ=os.environ to Pipeline, but failing steps are still retried only 3 times."
        ),
        "mutations": [
            ("flowkit/config.py", "import json\nfrom typing", "from typing"),
            (
                "flowkit/config.py",
                r'''        path = [p.lower() for p in name[len(ENV_PREFIX) :].split("__")]
        if not all(path):
            continue
        try:
            value = json.loads(raw)
        except ValueError:
            value = raw
''',
                r'''        path = name[len(ENV_PREFIX) :].lower().split("_")
        value = raw
''',
            ),
        ],
        "f2p": ["test_nested_int", "test_types_parsed", "test_three_levels_bool", "test_pipeline_uses_env_retries"],
    },
    {
        "id": "h2_12_business_days",
        "repo": "flowkit",
        "category": "edge_cases",
        "issue": (
            "`add_business_days(date(2024, 6, 3), -1)` returns 2024-06-03. I expected the previous "
            "business day, Friday 2024-05-31."
        ),
        "mutations": [
            ("flowkit/dates.py", "from datetime import date, datetime, timedelta\n", "from datetime import date, timedelta\n"),
            (
                "flowkit/dates.py",
                r'''def _day(x: date) -> date:
    return x.date() if isinstance(x, datetime) else x


''',
                "",
            ),
            (
                "flowkit/dates.py",
                r'''    hols = {_day(h) for h in holidays}

    def is_business_day(x: date) -> bool:
        return _day(x).weekday() < 5 and _day(x) not in hols

    if n == 0:
        while not is_business_day(d):
            d += timedelta(days=1)
        return d
    step = timedelta(days=1 if n > 0 else -1)
    for _ in range(abs(n)):
        d += step
        while not is_business_day(d):
            d += step
    return d
''',
                r'''    hols = set(holidays)

    def is_business_day(x: date) -> bool:
        return x.weekday() < 5 and x not in hols

    if n == 0:
        while not is_business_day(d):
            d += timedelta(days=1)
        return d
    for _ in range(n):
        d += timedelta(days=1)
        while not is_business_day(d):
            d += timedelta(days=1)
    return d
''',
            ),
        ],
        "f2p": ["test_backwards_simple", "test_backwards_over_weekend_and_holiday", "test_backwards_from_weekend", "test_datetime_with_holidays"],
    },
]
