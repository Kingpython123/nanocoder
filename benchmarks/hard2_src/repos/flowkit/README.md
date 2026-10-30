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
`a-b`, a step `*/n` or `a-b/n`, and comma-separated lists of these.

Matching follows classic crontab: minute, hour and month must always match. The two
day fields are special: a day field is *restricted* unless it starts with `*`
(so `*` and `*/2` are unrestricted). If both day fields are restricted, a day matches
when **either** of them matches (`0 9 1 * 1` = the 1st of every month and every
Monday). Otherwise both must match.

## Environment variables

`Pipeline(..., environ=os.environ)` (or `load_config(overrides, environ)`) also reads
variables named `FLOWKIT_<KEY>`. A double underscore separates nesting levels and names
are case-insensitive: `FLOWKIT_RETRY__MAX_RETRIES=5` sets `retry.max_retries`. Values are
parsed as JSON when they are valid JSON (`5`, `0.5`, `true`, `"x"`, `{"a": 1}`);
otherwise the raw string is used. Precedence: defaults < environment < explicit config.

## Templates

`{{ path.to.value | filter | filter(arg) }}`. Filters are applied left to right.
Available filters: `upper`, `lower`, `trim`, `default(value)`, `truncate(n)`.
A missing variable renders as an empty string unless `default` is used.
Filter arguments are Python literals; quoted strings may contain `|` and `}}`,
e.g. `{{ x | default('a | b') }}`.

## Events

`EventBus.emit()` calls handlers in subscription order. A handler that raises does not
stop the others; the first exception is re-raised after all handlers ran.

## Cache

`LRUCache(capacity, ttl=...)`: expired entries never count. When the cache is full,
expired entries are dropped before any live entry is evicted; `len()` and `keys()`
only report live entries.

## Running tests

    python -m pytest -q
