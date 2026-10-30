# flowkit

A tiny workflow toolkit: run steps in dependency order with retries, plus the
small utilities a scheduler needs (cron expressions, an LRU cache, an event bus,
string templates, date helpers).

## Modules

| Module | What it does |
|---|---|
| `flowkit.pipeline` | `Pipeline` runs `Step`s in dependency order, retrying failed steps |
| `flowkit.graph` | `topo_order()` dependency ordering, `CycleError` |
| `flowkit.config` | `DEFAULTS`, `load_config()`, `deep_merge()` |
| `flowkit.retry` | `retry()` with exponential backoff |
| `flowkit.cron` | `CronSpec` for 5-field cron expressions |
| `flowkit.cache` | `LRUCache` with optional TTL |
| `flowkit.events` | `EventBus` publish / subscribe |
| `flowkit.template` | `render("Hello {{ name | upper }}", ctx)` |
| `flowkit.dates` | `add_months()` and friends |

## Configuration

`Pipeline(steps, config={...})` merges the given config into `flowkit.config.DEFAULTS`
(nested dicts are merged key by key). Each pipeline gets its own copy; nothing a
pipeline does may change the defaults or another pipeline's config.

```python
DEFAULTS = {
    "name": "pipeline",
    "retry": {"max_retries": 3, "base_delay": 0.1, "max_delay": 2.0},
    "logging": {"level": "INFO", "handlers": {"console": {"enabled": True, "format": "%(message)s"}}},
}
```

## Cron syntax

Fields: minute (0-59), hour (0-23), day of month (1-31), month (1-12),
day of week (0-7, 0 and 7 are Sunday). Each field accepts `*`, a number, a range
`a-b`, a step `*/n` or `a-b/n`, and comma-separated lists of these. A time matches
when all five fields match.

## Templates

`{{ path.to.value | filter | filter(arg) }}`. Filters are applied left to right.
Available filters: `upper`, `lower`, `trim`, `default(value)`, `truncate(n)`.
A missing variable renders as an empty string unless `default` is used.

## Running tests

    python -m pytest -q
