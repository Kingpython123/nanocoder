"""构建 CI 修复评测集：从开源仓库的 PR 历史里找“CI 红，下一个提交只改源码就绿”的提交对。

    python benchmarks/build_ciset.py mine --out benchmarks/ciset_src/candidates.jsonl   # 只调 GitHub API
    python benchmarks/build_ciset.py logs                                               # 只调 GitHub API，存失败 job 的日志摘录
    python benchmarks/build_ciset.py validate --candidates ... --work ~/ciset           # 需要 docker，不调模型
    python benchmarks/build_ciset.py select --validated ... --out benchmarks/ciset/tasks.jsonl
    python benchmarks/build_ciset.py verify --work ~/ciset                              # 用锁定版本的配置再确认一遍

- mine：用 GraphQL 列出已合并 PR 里每个提交的 CI 状态，取“这个提交红、下一个提交同名检查全绿”的提交对，
  要求修复提交只改了不受保护的文件。这只是候选：CI 环境和我们的容器不一样，失败原因也可能是依赖或网络。
- logs：GitHub 只保留约 90 天日志。摘录不给 agent，只用来核对本地复现的和 CI 上是同一个失败。
- validate：在容器里各跑 3 次，确认修复前检查总是失败、打上人写的修复后总是通过。只有这样的才进评测集。
  specs.yml 写每题的检查命令（lint、类型检查要固定成 CI 用的工具版本）和人工排除的原因；只校验写了的候选。
- select：把依赖版本锁死写进配置，之后重跑不受新版本发布影响。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import threading
import time
import zlib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from nanocoder.bench.ci_run import _retry, checkout, materialize
from nanocoder.cifix.config import DEFAULT_PROTECTED, parse_config
from nanocoder.cifix.env import DockerEnv, EnvSetupError
from nanocoder.cifix.gates import protected_violations, run_checks, suppressions_added
from nanocoder.cifix.logs import extract_failure
from nanocoder.patch import apply_patch

HERE = Path(__file__).resolve().parent
REPOS = HERE / "ciset_src" / "repos.yml"
SPECS = HERE / "ciset_src" / "specs.yml"
CI_LOGS = HERE / "ciset_src" / "ci_logs"
BASE_IMAGE = "nanocoder-ci-base:3.12"
MAX_FILES, MAX_LINES = 8, 200
PAGES, MAX_PER_REPO = 8, 8
REPEATS = 3
SKIP_WORKFLOW = ("doc", "release", "publish", "label", "stale", "codeql", "pre-commit", "benchmark", "codspeed", "codecov", "coverage", "readthedocs", "changelog", "required-checks", "all-green", "alls-green", "check-success", "dco")
PR_QUERY = """query($owner:String!,$name:String!,$cursor:String){repository(owner:$owner,name:$name){pullRequests(states:[MERGED],first:25,after:$cursor,orderBy:{field:UPDATED_AT,direction:DESC}){pageInfo{hasNextPage endCursor} nodes{number commits(first:40){nodes{commit{oid committedDate parents(first:2){nodes{oid}} statusCheckRollup{state contexts(first:50){nodes{__typename ... on CheckRun{name conclusion databaseId checkSuite{workflowRun{databaseId workflow{name}}}} ... on StatusContext{context state}}}}}}}}}}}"""


def gh(path: str) -> object:
    for attempt in range(4):
        r = subprocess.run(["gh", "api", path], capture_output=True, text=True, encoding="utf-8", timeout=120)
        if r.returncode == 0:
            return json.loads(r.stdout)
        if "HTTP 404" in r.stderr or "HTTP 422" in r.stderr or "HTTP 410" in r.stderr:
            return None
        time.sleep(3 * (attempt + 1))
    print(f"  ! gh 失败：{path}：{r.stderr.strip()[:150]}", flush=True)
    return None


def pr_page(repo: str, cursor: str | None) -> dict | None:
    """一次取 25 个已合并 PR 的每个提交的 CI 状态。比逐个提交调 REST 省得多，也能看到 fork 来的 PR。"""
    owner, name = repo.split("/")
    args = ["gh", "api", "graphql", "-F", f"owner={owner}", "-F", f"name={name}", "-f", f"query={PR_QUERY}"]
    if cursor:
        args += ["-F", f"cursor={cursor}"]
    for attempt in range(5):
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=180)
        if r.returncode == 0:
            return json.loads(r.stdout)["data"]["repository"]["pullRequests"]
        time.sleep(4 * (attempt + 1))
    print(f"  ! graphql 失败：{repo}：{r.stderr.strip()[:150]}", flush=True)
    return None


def contexts(commit: dict) -> list[dict]:
    """把 CheckRun 和 StatusContext 统一成 name / ok / id，去掉和代码检查无关的。"""
    out = []
    for c in ((commit.get("statusCheckRollup") or {}).get("contexts") or {}).get("nodes", []):
        if c["__typename"] == "CheckRun":
            suite = (c.get("checkSuite") or {}).get("workflowRun") or {}
            item = {"name": c["name"], "state": c["conclusion"], "id": c["databaseId"], "run": suite.get("databaseId"), "workflow": (suite.get("workflow") or {}).get("name") or ""}
        else:
            item = {"name": c["context"], "state": c["state"], "id": None, "run": None, "workflow": ""}
        if not any(s in f"{item['workflow']} {item['name']}".lower() for s in SKIP_WORKFLOW):
            out.append(item)
    return out


def guess_kind(names: list[str]) -> str:
    text = " ".join(names).lower()
    if re.search(r"mypy|pyright|typ(e|ing)|\bty\b", text):
        return "type"
    if re.search(r"lint|ruff|flake|format|style|black|isort", text):
        return "lint"
    return "test"


def pair_to_candidate(repo: str, number: int, bad: dict, good: dict) -> dict | None:
    """bad 红、下一个提交 good 上同名检查全绿，且 good 只改了不受保护的文件。"""
    parents = [p["oid"] for p in good["parents"]["nodes"]]
    if parents != [bad["oid"]]:
        return None  # 合并提交混入了别的改动
    failed = [c for c in contexts(bad) if c["state"] in ("FAILURE", "ERROR", "TIMED_OUT")]
    after = {c["name"]: c["state"] for c in contexts(good)}
    if not failed or any(after.get(c["name"]) != "SUCCESS" for c in failed):
        return None
    detail = gh(f"repos/{repo}/commits/{good['oid']}")
    if not detail:
        return None
    files = detail.get("files", [])
    names = [f["filename"] for f in files]
    lines = sum(f["additions"] + f["deletions"] for f in files)
    if not 1 <= len(names) <= MAX_FILES or lines > MAX_LINES or not any(n.endswith(".py") for n in names):
        return None
    if protected_violations(names, DEFAULT_PROTECTED):
        return None
    return {
        "repo": repo, "pr": number, "base": bad["oid"], "fix": good["oid"], "run_id": failed[0]["run"], "workflow": failed[0]["workflow"],
        "created_at": bad["committedDate"], "failed_jobs": [{"id": c["id"], "name": c["name"], "steps": []} for c in failed],
        "files": names, "lines": lines, "fix_message": detail["commit"]["message"].split("\n")[0][:120],
        "guess_kind": guess_kind([c["name"] for c in failed]),
    }  # fmt: skip


def mine_repo(repo: str, pages: int, known: set[str], out: Path, lock: threading.Lock) -> None:
    cursor, found, examined = None, 0, 0
    for _ in range(pages):
        data = pr_page(repo, cursor)
        if not data:
            break
        for pr in data["nodes"]:
            commits = [n["commit"] for n in pr["commits"]["nodes"]]
            for bad, good in zip(commits, commits[1:]):
                if (bad.get("statusCheckRollup") or {}).get("state") not in ("FAILURE", "ERROR") or bad["oid"] in known:
                    continue
                examined += 1
                candidate = pair_to_candidate(repo, pr["number"], bad, good)
                if candidate and found < MAX_PER_REPO:
                    found += 1
                    with lock, out.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(candidate, ensure_ascii=False) + "\n")
                    print(f"  + {repo}#{pr['number']} {bad['oid'][:8]} {candidate['guess_kind']} {candidate['fix_message'][:60]}", flush=True)
        if found >= MAX_PER_REPO or not data["pageInfo"]["hasNextPage"]:
            break
        cursor = data["pageInfo"]["endCursor"]
    print(f"{repo}: 看了 {examined} 个红提交，候选 {found}", flush=True)


def mine(out: Path, pages: int = PAGES) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    known = {c["base"] for c in load_jsonl(out)}
    repos = [e["repo"] for e in yaml.safe_load(REPOS.read_text(encoding="utf-8"))]
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda repo: mine_repo(repo, pages, known, out, lock), repos))


def fetch_logs(candidates: Path) -> None:
    """存每题失败 job 的日志摘录和原始长度，日志过期的记为 expired。"""
    CI_LOGS.mkdir(parents=True, exist_ok=True)
    index_path = CI_LOGS / "index.jsonl"
    index = load_jsonl(index_path)
    done = {r["base"] for r in index}
    for c in load_jsonl(candidates):
        if c["base"] in done:
            continue
        sizes, parts = [], []
        for job in c["failed_jobs"][:3]:
            r = subprocess.run(["gh", "api", f"repos/{c['repo']}/actions/jobs/{job['id']}/logs"], capture_output=True, timeout=180)
            if r.returncode != 0:
                continue
            text = r.stdout.decode("utf-8", "replace")
            sizes.append(len(text))
            parts.append(f"===== {job['name']} =====\n{extract_failure(text)}")
        if parts:
            (CI_LOGS / f"{c['base'][:8]}.txt").write_text("\n\n".join(parts), encoding="utf-8")
        row = {"base": c["base"], "repo": c["repo"], "raw_chars": sizes, "expired": not parts}
        with index_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        print(f"{c['repo']} {c['base'][:8]}: {'过期或没有失败 job' if not parts else sizes}", flush=True)


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def load_specs() -> dict[str, dict]:
    if not SPECS.exists():
        return {}
    return {s["base"]: s for s in yaml.safe_load(SPECS.read_text(encoding="utf-8")) or []}


def spec_for(base: str, specs: dict[str, dict]) -> dict:
    return next((s for prefix, s in specs.items() if base.startswith(prefix)), {})


def config_for(entry: dict, spec: dict) -> dict:
    """spec 的检查放前面；lint、类型检查类的题也跑测试，防止修 lint 时弄坏功能。"""
    checks = list(spec.get("checks", []))
    if not spec.get("no_test"):
        checks.append({"name": "test", "command": spec.get("test") or entry["test"]})
    return {
        "image": spec.get("image", BASE_IMAGE),
        "setup": [spec.get("setup") or entry["setup"], *spec.get("extra_setup", [])],
        "checks": checks,
        "limits": {"check_timeout": 300, "setup_timeout": 420},
    }


def validate(candidates: Path, work: Path, out: Path, shard: tuple[int, int] = (0, 1)) -> None:
    """shard：可以开几个进程并行校验。按仓库分片，同一个裸克隆不会被同时 fetch。"""
    entries = {e["repo"]: e for e in yaml.safe_load(REPOS.read_text(encoding="utf-8"))}
    specs = load_specs()
    done = {r["base"] for r in load_jsonl(out)}
    for c in load_jsonl(candidates):
        if c["base"] in done or zlib.crc32(c["repo"].encode()) % shard[1] != shard[0]:
            continue
        done.add(c["base"])  # 同一提交可能在多个 PR 里
        spec = spec_for(c["base"], specs)
        if not spec:
            continue  # 候选够用，只校验 specs.yml 里写了的
        entry = entries[c["repo"]]
        if spec.get("skip"):
            verdict = {"verdict": "excluded", "note": spec["skip"]}
        else:
            verdict = validate_one(c, config_for(entry, spec), work)
        row = {**c, **verdict, "kind": spec.get("kind", "test"), "config": config_for(entry, spec)}
        with out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"{c['repo']}#{c['pr']} {c['base'][:8]}: {verdict['verdict']} {verdict.get('note', '')[:110]}", flush=True)


def validate_one(c: dict, raw_config: dict, work: Path, repeats: int = REPEATS) -> dict:
    """修复前后各跑 repeats 次，每次都是新容器。只有一直红、一直绿的检查才算数。"""
    config = parse_config(raw_config)
    try:
        bare = checkout(work, c["repo"], c["base"], c["fix"])
        diff = _retry(["git", "-C", str(bare), "diff", "--binary", c["base"], c["fix"]], timeout=300)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        return {"verdict": "fetch_failed", "note": str(e)[:200]}
    gold = diff.stdout.decode("utf-8", "replace")
    suppressed = suppressions_added(gold)
    if suppressed:
        return {"verdict": "gold_suppression", "note": "官方修复本身用了屏蔽写法，产品闸门会拒绝：" + " | ".join(suppressed[:3])}
    with tempfile.TemporaryDirectory(dir=work) as tmp:
        repo = Path(tmp) / "repo"
        materialize(bare, c["base"], repo)
        env = DockerEnv(repo, config)
        try:
            env.prepare()
            before_runs, after_runs = [], []
            for _ in range(repeats):
                with env.open() as box:
                    before_runs.append(run_checks(box, config.checks, config.limits.check_timeout))
            for _ in range(repeats):
                with env.open() as box:
                    error = apply_patch(box, gold)
                    if error:
                        return {"verdict": "gold_not_applied", "note": error[:200]}
                    after_runs.append(run_checks(box, config.checks, config.limits.check_timeout))
            with env.open() as box:
                freeze = box.run("pip freeze --exclude-editable", timeout=60).output
            return judge(config, before_runs, after_runs) | {"freeze": freeze.split(), "gold_diff": gold}
        except EnvSetupError as e:
            return {"verdict": "setup_failed", "note": str(e)[-200:]}
        finally:
            env.close()


def judge(config, before_runs: list, after_runs: list) -> dict:
    """target 是修复前一直红、修复后一直绿的检查；修复后还红的检查从任务里去掉（修复前就坏，和这题无关）。"""
    reds = {c.name: sum(not run[i].passed for run in before_runs) for i, c in enumerate(config.checks)}
    fails_after = {c.name: sum(not run[i].passed for run in after_runs) for i, c in enumerate(config.checks)}
    timed_out = [r.name for run in before_runs + after_runs for r in run if r.timed_out]
    counts = {"base_red": reds, "gold_red": fails_after}
    n = len(before_runs)
    target = [name for name, red in reds.items() if red == n and fails_after[name] == 0]
    flaky = [name for name in reds if 0 < reds[name] < n or 0 < fails_after[name] < n]
    if timed_out:
        return {"verdict": "timeout", "note": f"超时：{sorted(set(timed_out))}", **counts}
    if flaky:
        return {"verdict": "flaky", "note": f"同一提交结果不稳定：{flaky}", **counts}
    if not any(reds.values()):
        return {"verdict": "base_passes", "note": "修复前检查通过（CI 环境和容器不同，或失败发生在没跑的检查里）", **counts}
    if not target:
        return {"verdict": "gold_fails", "note": "官方修复后仍失败：" + after_runs[0][0].output[-150:], **counts}
    keep = [c.name for c in config.checks if fails_after[c.name] == 0]
    last = next(r for r in before_runs[0] if r.name == target[0])
    tail = last.output.strip().splitlines()[-1][:110] if last.output.strip() else ""
    return {"verdict": "valid", "note": tail, "target_checks": target, "kept_checks": keep, "before_chars": {r.name: len(r.output) for r in before_runs[0]}, **counts}


def pinned(row: dict) -> dict:
    """先按 freeze 装好固定版本，原来的 setup 再跑时不会升级它们。去掉修复后还红的检查。"""
    config = dict(row["config"])
    pins = [p for p in row.get("freeze", []) if "==" in p]
    config["setup"] = [f"pip install -q --no-deps {' '.join(pins)}", *config["setup"]] if pins else config["setup"]
    config["checks"] = [c for c in config["checks"] if c["name"] in row["kept_checks"]]
    return config


def select(validated: Path, out: Path, per_repo: int, total: int) -> None:
    rows = load_jsonl(validated)
    print(Counter(r["verdict"] for r in rows))
    chosen, counts = [], Counter()
    for r in sorted((r for r in rows if r["verdict"] == "valid"), key=lambda r: r["created_at"], reverse=True):
        if counts[r["repo"]] < per_repo and len(chosen) < total:
            counts[r["repo"]] += 1
            chosen.append({**r, "config": pinned(r), "id": f"{r['repo'].replace('/', '__')}-{r['pr']}-{r['base'][:8]}"})
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in chosen), encoding="utf-8")
    print(f"选了 {len(chosen)} 题：{dict(counts)}，类型：{dict(Counter(r['kind'] for r in chosen))}")


def verify(tasks: Path, work: Path) -> int:
    """最终配置（版本锁死）下再确认一次红和绿。"""
    bad = 0
    for t in load_jsonl(tasks):
        v = validate_one(t, t["config"], work, repeats=1)
        ok = v["verdict"] == "valid"
        bad += not ok
        print(f"{t['id']}: {v['verdict']} {'' if ok else v.get('note', '')[:200]}", flush=True)
    print(f"不合格 {bad} 题")
    return 1 if bad else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("mine")
    p.add_argument("--out", type=Path, default=HERE / "ciset_src" / "candidates.jsonl")
    p.add_argument("--pages", type=int, default=PAGES)
    p = sub.add_parser("logs")
    p.add_argument("--candidates", type=Path, default=HERE / "ciset_src" / "candidates.jsonl")
    p = sub.add_parser("verify")
    p.add_argument("--tasks", type=Path, default=HERE / "ciset" / "tasks.jsonl")
    p.add_argument("--work", type=Path, required=True)
    p = sub.add_parser("validate")
    p.add_argument("--candidates", type=Path, default=HERE / "ciset_src" / "candidates.jsonl")
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--out", type=Path, default=HERE / "ciset_src" / "validated.jsonl")
    p.add_argument("--shard", default="0/1", help="i/n")
    p = sub.add_parser("select")
    p.add_argument("--validated", type=Path, default=HERE / "ciset_src" / "validated.jsonl")
    p.add_argument("--out", type=Path, default=HERE / "ciset" / "tasks.jsonl")
    p.add_argument("--per-repo", type=int, default=3)
    p.add_argument("--total", type=int, default=20)
    args = parser.parse_args()
    if args.command == "mine":
        mine(args.out, args.pages)
    elif args.command == "logs":
        fetch_logs(args.candidates)
    elif args.command == "verify":
        return verify(args.tasks, args.work.expanduser())
    elif args.command == "validate":
        args.work = args.work.expanduser()
        args.work.mkdir(parents=True, exist_ok=True)
        i, n = args.shard.split("/")
        validate(args.candidates, args.work, args.out, (int(i), int(n)))
    else:
        select(args.validated, args.out, args.per_repo, args.total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
