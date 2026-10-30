"""Currency conversion with a rate cache."""

from __future__ import annotations

from decimal import Decimal
from typing import Mapping, Protocol

from .money import round_money, to_decimal


class RateProvider(Protocol):
    def get_rate(self, src: str, dst: str) -> Decimal: ...


class StaticRates:
    """Rates from a dict {(src, dst): rate}. Inverse pairs are derived automatically.

    `calls` counts get_rate() calls so callers can check caching.
    """

    def __init__(self, rates: Mapping[tuple[str, str], object]):
        self._rates = {(s.upper(), d.upper()): to_decimal(r) for (s, d), r in rates.items()}
        self.calls = 0

    def get_rate(self, src: str, dst: str) -> Decimal:
        self.calls += 1
        src, dst = src.upper(), dst.upper()
        if src == dst:
            return Decimal(1)
        if (src, dst) in self._rates:
            return self._rates[(src, dst)]
        if (dst, src) in self._rates:
            return Decimal(1) / self._rates[(dst, src)]
        raise KeyError(f"no exchange rate for {src}->{dst}")


class Converter:
    """Converts amounts between currencies. Rates are fetched from the provider only once."""

    def __init__(self, provider: RateProvider):
        self.provider = provider
        self._cache: dict = {}

    def rate(self, src: str, dst: str) -> Decimal:
        key = (src.upper(), dst.upper())
        if key not in self._cache:
            self._cache[key] = self.provider.get_rate(*key)
        return self._cache[key]

    def convert(self, amount: object, src: str, dst: str) -> Decimal:
        """Convert `amount` from currency `src` to currency `dst`, rounded to cents."""
        return round_money(to_decimal(amount) * self.rate(src, dst))

    def clear(self) -> None:
        self._cache.clear()
