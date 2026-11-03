"""配对比较两次运行（消融实验用）。

    python -m nanocoder.bench.compare hard2-baseline-k3 hard2-e8-spec-k3

两次运行必须跑的是同一批题。按题配对：每题算两边的解决率，差值的平均就是 Δpass@1；
置信区间用"按题重采样"的 bootstrap（题是独立单位，同一题的多次运行不独立）。
另外给出符号检验：只看两边结果不同的题，B 更好的题数是否显著多于 A。
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from collections import defaultdict

from miniagent.console import setup_console

from .__main__ import INFRA_FAILURES, RUNS_DIR, load_results


def per_task(run_id: str) -> dict[str, list[bool]]:
    results = load_results(RUNS_DIR / run_id)
    if not results:
        raise SystemExit(f"runs/{run_id} 没有结果")
    infra = [r for r in results if r.get("exit_reason") in INFRA_FAILURES]
    if infra:
        print(f"⚠ runs/{run_id} 有 {len(infra)} 次基础设施故障（{', '.join(INFRA_FAILURES)}），"
              f"结果不可靠；先用 --retry-errors 重跑")
    by_task: dict[str, list[bool]] = defaultdict(list)
    for r in results:
        by_task[r["instance_id"]].append(bool(r.get("resolved")))
    return by_task


def avg(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def bootstrap_ci(diffs: list[float], n: int = 10_000, seed: int = 0) -> tuple[float, float]:
    rng = random.Random(seed)
    means = sorted(avg([rng.choice(diffs) for _ in diffs]) for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n) - 1]


def sign_test(wins: int, losses: int) -> float:
    """双侧精确符号检验的 p 值。"""
    n = wins + losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * p)


def main() -> int:
    setup_console()
    p = argparse.ArgumentParser(description="配对比较两次运行")
    p.add_argument("run_a", help="对照组 run_id")
    p.add_argument("run_b", help="实验组 run_id")
    args = p.parse_args()

    a, b = per_task(args.run_a), per_task(args.run_b)
    common = sorted(set(a) & set(b))
    only = sorted(set(a) ^ set(b))
    if not common:
        raise SystemExit("两次运行没有共同的题，没法配对比较")
    if only:
        print(f"⚠ 只在一边出现的题（不参与比较）：{', '.join(only)}")

    rows, diffs, wins, losses = [], [], 0, 0
    for t in common:
        ra, rb = avg(a[t]), avg(b[t])
        diffs.append(rb - ra)
        wins += rb > ra
        losses += rb < ra
        mark = "↑" if rb > ra else "↓" if rb < ra else " "
        rows.append(f"  {mark} {t:<34} {sum(a[t])}/{len(a[t])} -> {sum(b[t])}/{len(b[t])}")

    pa = avg([avg(a[t]) for t in common])
    pb = avg([avg(b[t]) for t in common])
    lo, hi = bootstrap_ci(diffs)
    print(f"A = {args.run_a}\nB = {args.run_b}\n共同题数 {len(common)}\n")
    print("\n".join(rows))
    print(f"\npass@1：A {pa:.1%}  B {pb:.1%}  Δ = {pb - pa:+.1%}（95% CI {lo:+.1%} ~ {hi:+.1%}，按题 bootstrap）")
    print(f"B 更好 {wins} 题，A 更好 {losses} 题，持平 {len(common) - wins - losses} 题；符号检验 p = {sign_test(wins, losses):.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
