"""hard 任务集的定义：每个任务 = 一个基础仓库 + 注入的 bug + 模糊的 issue + 隐藏测试。

- repos/<repo>/        正确的代码和可见的回归测试（agent 能看到、能跑）
- hidden/<id>/         隐藏测试，只在评测时覆盖进仓库（和 SWE-bench 一样，agent 看不到）
- MUTATIONS            把正确代码改成有 bug 的版本；参考答案就是原始文件

隐藏测试文件里，名字列在 f2p 里的是 FAIL_TO_PASS，其余都是 PASS_TO_PASS：
它们在有 bug 的代码上也能通过，用来抓"修好了一个、改坏了另一个"的回归（陷阱）。

由 benchmarks/build_hard.py 生成 benchmarks/hard/<id>/。
"""

TASKS = [
    # ---------------------------------------------------------------- ledgerlite
    {
        "id": "hard01_money_rounding",
        "repo": "ledgerlite",
        "category": "spec",
        "issue": (
            "Our accountant flagged some invoices: a single line of 1 x 2.675 is billed as 2.67, "
            "and 1 x 0.125 shows up as 0.12. Every other tool we use gives 2.68 and 0.13. "
            "Refunds (negative amounts) seem to have the same problem."
        ),
        "mutations": [
            (
                "ledgerlite/money.py",
                "    return to_decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)\n",
                "    return Decimal(str(round(float(to_decimal(value)), 2))).quantize(CENT)\n",
            ),
            (
                "ledgerlite/money.py",
                "from decimal import ROUND_HALF_UP, Decimal, InvalidOperation\n",
                "from decimal import Decimal, InvalidOperation\n",
            ),
        ],
        "f2p": ["test_half_cent_rounds_up", "test_negative_half_cent", "test_invoice_line_total", "test_large_amount_precision"],
    },
    {
        "id": "hard02_currency_cache",
        "repo": "ledgerlite",
        "category": "state",
        "issue": (
            "In a long-running worker, after converting EUR to USD, converting EUR to GBP returns "
            "the USD figure (100 EUR -> 110.00 'GBP'). Restarting the worker makes the first "
            "conversion correct again. Note the rate provider is a paid API, so we can't afford "
            "to call it more than once per currency pair."
        ),
        "mutations": [
            (
                "ledgerlite/currency.py",
                "        key = (src.upper(), dst.upper())\n"
                "        if key not in self._cache:\n"
                "            self._cache[key] = self.provider.get_rate(*key)\n",
                "        key = src.upper()\n"
                "        if key not in self._cache:\n"
                "            self._cache[key] = self.provider.get_rate(key, dst.upper())\n",
            ),
        ],
        "f2p": ["test_same_source_different_targets", "test_one_provider_call_per_pair"],
    },
    {
        "id": "hard03_discount_stacking",
        "repo": "ledgerlite",
        "category": "spec",
        "issue": (
            "Stacked coupons are calculated wrong. A 100.00 order with two 10% coupons is charged "
            "80.00, which doesn't follow our documented discount rules. Two 50% coupons even make "
            "the order free."
        ),
        "mutations": [
            (
                "ledgerlite/discounts.py",
                "    for d in percents:\n        result -= result * d.value / 100\n",
                "    total_percent = sum((d.value for d in percents), Decimal(0))\n"
                "    result -= result * total_percent / 100\n",
            ),
        ],
        "f2p": ["test_two_ten_percent", "test_two_fifty_percent", "test_invoice_with_stacked_coupons", "test_rounding_once_at_end"],
    },
    {
        "id": "hard04_csv_quotes",
        "repo": "ledgerlite",
        "category": "robustness",
        "issue": (
            "Importing a line-item CSV exported from Excel fails:\n\n"
            "    ValueError: row 2: invalid literal for int() with base 10: '2m\"'\n\n"
            "The row is `C-7,\"Cable, 2m\",3,4.99` (sku, description, quantity, unit_price). "
            "Excel quotes fields that contain commas, quotes or line breaks."
        ),
        "mutations": [
            (
                "ledgerlite/importer.py",
                "    reader = csv.reader(io.StringIO(text))\n"
                "    rows = [row for row in reader if row and any(cell.strip() for cell in row)]\n",
                '    rows = [line.split(",") for line in text.splitlines() if line.strip()]\n',
            ),
            ("ledgerlite/importer.py", "import csv\nimport io\n\n", ""),
        ],
        "f2p": ["test_quoted_comma", "test_escaped_quotes", "test_newline_inside_quotes"],
    },
    {
        "id": "hard05_tax_exempt",
        "repo": "ledgerlite",
        "category": "logic",
        "issue": (
            "We are under-charging VAT: lines with category 'e-books' and 'seafood' come out with "
            "zero tax. Only the categories listed in the tax rules should be exempt."
        ),
        "mutations": [
            (
                "ledgerlite/tax.py",
                "    return normalize_category(category) in EXEMPT_CATEGORIES\n",
                "    category = normalize_category(category)\n"
                "    return any(exempt in category for exempt in EXEMPT_CATEGORIES)\n",
            ),
        ],
        "f2p": ["test_similar_categories_are_taxed"],
    },
    {
        "id": "hard06_aging_boundary",
        "repo": "ledgerlite",
        "category": "multi_location",
        "issue": (
            "Collections complained that an invoice that is exactly 30 days past due shows up as "
            "31-60 in the aging numbers, so it gets the second dunning letter too early. "
            "I suspect 60 and 90 days are off as well."
        ),
        "mutations": [
            (
                "ledgerlite/aging.py",
                "    if days <= 30:\n        return \"1-30\"\n    if days <= 60:\n"
                "        return \"31-60\"\n    if days <= 90:\n",
                "    if days < 30:\n        return \"1-30\"\n    if days < 60:\n"
                "        return \"31-60\"\n    if days < 90:\n",
            ),
            (
                "ledgerlite/aging.py",
                "        if days <= 30:\n            label = \"1-30\"\n        elif days <= 60:\n"
                "            label = \"31-60\"\n        elif days <= 90:\n",
                "        if days < 30:\n            label = \"1-30\"\n        elif days < 60:\n"
                "            label = \"31-60\"\n        elif days < 90:\n",
            ),
        ],
        "f2p": ["test_summary_boundaries", "test_overdue_list_boundaries"],
    },
    {
        "id": "hard07_report_direction",
        "repo": "ledgerlite",
        "category": "multi_file",
        "issue": (
            "The receivables report in EUR lists a 110.00 USD invoice as 121.00 EUR. "
            "With EUR/USD at 1.10 it should be 100.00 EUR. The grand total is wrong as a result."
        ),
        "mutations": [
            (
                "ledgerlite/report.py",
                "converter.convert(inv.total, inv.currency, base_currency)",
                "converter.convert(inv.total, base_currency, inv.currency)",
            ),
        ],
        "f2p": ["test_foreign_invoice_converted_to_base", "test_render_mixed_currencies"],
    },
    # ---------------------------------------------------------------- flowkit
    {
        "id": "hard08_self_dependency",
        "repo": "flowkit",
        "category": "logic",
        "issue": (
            "A pipeline step that lists itself in depends_on (a typo in our YAML) is silently "
            "accepted and runs normally. Any other circular dependency is rejected with a "
            "CycleError, and this should be too."
        ),
        "mutations": [
            (
                "flowkit/graph.py",
                "    graph = {node: sorted(set(ds)) for node, ds in deps.items()}\n",
                "    graph = {node: sorted(set(ds) - {node}) for node, ds in deps.items()}\n",
            ),
        ],
        "f2p": ["test_self_loop_is_cycle", "test_pipeline_rejects_self_dependency"],
    },
    {
        "id": "hard09_config_leak",
        "repo": "flowkit",
        "category": "state",
        "issue": (
            "Creating one Pipeline with config={'retry': {'max_retries': 5}} changes the retry "
            "settings of every Pipeline created afterwards in the same process. Also, setting just "
            "logging.handlers.console.enabled=False loses the console format setting."
        ),
        "mutations": [
            (
                "flowkit/config.py",
                "    result: dict[str, Any] = {}\n"
                "    for key, value in base.items():\n"
                "        result[key] = deep_merge(value, {}) if isinstance(value, Mapping) else value\n"
                "    for key, value in override.items():\n"
                "        if isinstance(value, Mapping) and isinstance(result.get(key), dict):\n"
                "            result[key] = deep_merge(result[key], value)\n"
                "        elif isinstance(value, Mapping):\n"
                "            result[key] = deep_merge(value, {})\n"
                "        else:\n",
                "    result: dict[str, Any] = dict(base)\n"
                "    for key, value in override.items():\n"
                "        if isinstance(value, Mapping) and isinstance(result.get(key), dict):\n"
                "            result[key].update(value)\n"
                "        else:\n",
            ),
        ],
        "f2p": ["test_defaults_not_mutated", "test_pipelines_isolated", "test_three_level_merge"],
    },
    {
        "id": "hard10_retry_attempts",
        "repo": "flowkit",
        "category": "regression_trap",
        "issue": (
            "retry(fn, max_retries=3) gives up after the 3rd call. According to its docstring it "
            "should retry 3 times after the first failure. With max_retries=0 it crashes with "
            "\"TypeError: exceptions must derive from BaseException\" instead of raising fn's error."
        ),
        "mutations": [
            (
                "flowkit/retry.py",
                "    for attempt in range(max_retries + 1):\n"
                "        try:\n"
                "            return fn()\n"
                "        except retry_on:\n"
                "            if attempt == max_retries:\n"
                "                raise\n"
                "            sleep(delays[attempt])\n"
                "    raise AssertionError(\"unreachable\")\n",
                "    last_error = None\n"
                "    for attempt in range(max_retries):\n"
                "        try:\n"
                "            return fn()\n"
                "        except retry_on as e:\n"
                "            last_error = e\n"
                "            if attempt < max_retries - 1:\n"
                "                sleep(delays[attempt])\n"
                "    raise last_error\n",
            ),
        ],
        "f2p": ["test_total_calls", "test_sleeps_between_attempts_only", "test_zero_retries", "test_succeeds_on_last_attempt"],
    },
    {
        "id": "hard11_template_filters",
        "repo": "flowkit",
        "category": "spec",
        "issue": (
            "`{{ name | default('anonymous') | upper }}` renders 'anonymous' when name is missing, "
            "but I expected 'ANONYMOUS'. Chained filters in general behave strangely."
        ),
        "mutations": [
            ("flowkit/template.py", "        for f in filters:\n", "        for f in reversed(filters):\n"),
        ],
        "f2p": ["test_default_then_upper", "test_default_then_truncate", "test_trim_then_truncate", "test_lower_then_default"],
    },
    {
        "id": "hard12_cron_range_step",
        "repo": "flowkit",
        "category": "spec",
        "issue": (
            "CronSpec('10-30/10 * * * *') raises CronError: bad cron item '10-30/10'. "
            "That's standard cron syntax (should fire at minutes 10, 20 and 30)."
        ),
        "mutations": [
            (
                "flowkit/cron.py",
                '        rng, _, step_text = part.partition("/")\n',
                '        rng, step_text = part, ""\n'
                '        if part.startswith("*/"):\n'
                '            rng, _, step_text = part.partition("/")\n',
            ),
        ],
        "f2p": ["test_range_with_step", "test_weekday_range_step", "test_list_of_ranges_with_steps", "test_hour_range_step"],
    },
    {
        "id": "hard13_lru_recency",
        "repo": "flowkit",
        "category": "regression_trap",
        "issue": (
            "Our hot keys keep getting evicted from LRUCache even though they are read on every "
            "request. It behaves like a FIFO queue instead of an LRU."
        ),
        "mutations": [
            (
                "flowkit/cache.py",
                "            return default\n        self._data.move_to_end(key)\n        self.hits += 1\n",
                "            return default\n        self.hits += 1\n",
            ),
        ],
        "f2p": ["test_get_refreshes_recency", "test_keys_order_after_get"],
    },
    {
        "id": "hard14_add_months_clamp",
        "repo": "flowkit",
        "category": "boundary",
        "issue": (
            "Scheduling a monthly job that starts on 2024-01-31 crashes with "
            "\"ValueError: day is out of range for month\" when computing the next run."
        ),
        "mutations": [
            (
                "flowkit/dates.py",
                "    day = min(d.day, calendar.monthrange(year, month0 + 1)[1])\n"
                "    return d.replace(year=year, month=month0 + 1, day=day)\n",
                "    return d.replace(year=year, month=month0 + 1)\n",
            ),
        ],
        "f2p": ["test_clamps_to_month_end", "test_leap_years", "test_negative_months_clamp", "test_datetime_clamp_keeps_time"],
    },
    {
        "id": "hard15_event_once",
        "repo": "flowkit",
        "category": "state",
        "issue": (
            "When a `once=True` subscriber fires, the next subscriber for the same event doesn't "
            "get that event. Same thing if a handler unsubscribes itself while handling an event."
        ),
        "mutations": [
            (
                "flowkit/events.py",
                "        handlers = list(self._handlers.get(event, ()))\n",
                "        handlers = self._handlers.get(event, [])\n",
            ),
        ],
        "f2p": ["test_once_does_not_skip_next", "test_self_unsubscribe_does_not_skip_next", "test_emit_count_with_once", "test_subscribe_during_emit"],
    },
    {
        "id": "hard16_zero_retries_config",
        "repo": "flowkit",
        "category": "multi_file",
        "issue": (
            "We set config={'retry': {'max_retries': 0}} on a Pipeline because the step is not "
            "idempotent, but a failing step is still retried 3 times. Setting it to 5 works."
        ),
        "mutations": [
            (
                "flowkit/pipeline.py",
                '                max_retries=retry_cfg["max_retries"],\n'
                '                base_delay=retry_cfg["base_delay"],\n',
                '                max_retries=retry_cfg.get("max_retries") or 3,\n'
                '                base_delay=retry_cfg.get("base_delay") or 0.1,\n',
            ),
        ],
        "f2p": ["test_zero_retries_from_config", "test_zero_base_delay_from_config"],
    },
]
