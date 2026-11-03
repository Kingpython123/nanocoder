"""从 SWE-bench Verified（500 题）里抽一个固定的子集，按仓库分层、比例与全集一致。

    python benchmarks/swebench/make_subset.py --n 50 --seed 42 --out verified50

子集一旦用来跑实验就不要再改（换子集 = 换一个新名字），否则前后结果没法比较。
"""

from __future__ import annotations

import argparse
import random
from collections import defaultdict
from pathlib import Path

from datasets import load_dataset

HERE = Path(__file__).resolve().parent


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=50)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", default="verified50")
    args = p.parse_args()

    ds = load_dataset("SWE-bench/SWE-bench_Verified", split="test")
    by_repo: dict[str, list[str]] = defaultdict(list)
    for row in ds:
        by_repo[row["repo"]].append(row["instance_id"])
    total = len(ds)

    # 最大余数法分配名额：每个仓库 floor(比例)，剩下的名额给余数最大的仓库
    quotas = {repo: args.n * len(ids) / total for repo, ids in by_repo.items()}
    alloc = {repo: int(q) for repo, q in quotas.items()}
    for repo in sorted(quotas, key=lambda r: quotas[r] - alloc[r], reverse=True)[: args.n - sum(alloc.values())]:
        alloc[repo] += 1

    rng = random.Random(args.seed)
    chosen = []
    for repo in sorted(by_repo):
        chosen += rng.sample(sorted(by_repo[repo]), alloc[repo])
    lines = [f"# SWE-bench Verified subset: n={args.n}, seed={args.seed}, stratified by repo", *sorted(chosen)]
    (HERE / f"{args.out}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print({r: a for r, a in sorted(alloc.items()) if a}, "->", len(chosen))


if __name__ == "__main__":
    main()
