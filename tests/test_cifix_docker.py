"""端到端：真实 docker + 演示仓库 + 写死行为的假 agent，不调模型。没有 docker 时跳过。"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from nanocoder.agent import AgentResult
from nanocoder.cifix.config import load_config
from nanocoder.cifix.env import DockerEnv
from nanocoder.cifix.runner import FIXED, NOT_GREEN, NOT_REPRODUCED, PROTECTED_PATH, SETUP_FAILED, SUPPRESSION, fix_ci

DEMO = Path(__file__).resolve().parents[1] / "examples" / "ci-demo"
BUG = 'discounted.quantize(Decimal("0.01"))'
GOOD_FIX = 'discounted.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)'


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    return subprocess.run(["docker", "info"], capture_output=True, timeout=30).returncode == 0


pytestmark = pytest.mark.skipif(not _docker_available(), reason="需要 docker")


def make_repo(tmp_path: Path, fixed: bool = False) -> Path:
    repo = tmp_path / "repo"
    shutil.copytree(DEMO, repo)
    # /mnt/e 上的文件在 WSL 里都带可执行位，ruff 会报 EXE002
    for path in repo.rglob("*"):
        if path.is_file():
            path.chmod(0o644)
    if fixed:
        path = repo / "invoice.py"
        path.write_text(path.read_text(encoding="utf-8").replace(BUG, GOOD_FIX), encoding="utf-8")
    subprocess.run(
        "git init -q && git add -A && git -c user.name=t -c user.email=t@example.com commit -q -m init",
        shell=True, cwd=repo, check=True,
    )  # fmt: skip
    # 没提交的文件不能进容器
    (repo / ".env").write_text("OPENAI_API_KEY=not-a-real-key\n", encoding="utf-8")
    return repo


def scripted(*edits, seen: list | None = None):
    """假 agent：按顺序改文件，然后提交。"""

    def run(task, sandbox):
        if seen is not None:
            seen.append(sandbox.run("ls -a; env; curl --version >/dev/null 2>&1; python -c \"import socket; socket.create_connection(('1.1.1.1', 53), 3)\"; echo net=$?", timeout=30).output)
        for path, old, new in edits:
            sandbox.write_file(path, sandbox.read_file(path).replace(old, new))
        return AgentResult(exit_reason="submitted", messages=[])

    return run


@pytest.fixture(scope="module")
def real_config():
    return load_config(DEMO / ".nanocoder.yml")


@pytest.fixture(scope="module")
def config(real_config):
    """装依赖要两三分钟：只装一次，保存成镜像，其余用例从它开始。真实的 setup 流程由第一个用例覆盖。"""
    tag = "nanocoder-test-base:latest"
    name = "nanocoder-test-base-builder"
    subprocess.run(["docker", "run", "-d", "--rm", "--name", name, "--entrypoint", "sleep", real_config.image, "infinity"], check=True, capture_output=True)
    try:
        for command in real_config.setup:
            subprocess.run(["docker", "exec", name, "bash", "-c", command], check=True, capture_output=True, timeout=900)
        subprocess.run(["docker", "commit", name, tag], check=True, capture_output=True)
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    yield replace(real_config, image=tag, setup=())
    subprocess.run(["docker", "rmi", "-f", tag], capture_output=True)


def test_real_fix_goes_green_and_sandbox_has_no_secrets_or_network(tmp_path, real_config):
    config = real_config
    seen: list[str] = []
    outcome = fix_ci(DockerEnv(make_repo(tmp_path), config), config, scripted(("invoice.py", BUG, GOOD_FIX), seen=seen))
    assert outcome.status == FIXED, outcome.detail
    assert outcome.changed_files == ["invoice.py"]
    assert {r.name: r.passed for r in outcome.before} == {"test": False, "lint": True}
    assert all(r.passed for r in outcome.after)
    listing = seen[0]
    assert ".env" not in listing.split() and "OPENAI_API_KEY" not in listing
    assert "net=0" not in listing


def test_flaky_or_already_green_is_not_reproduced(tmp_path, config):
    def must_not_run(task, sandbox):
        raise AssertionError("agent should not run")

    outcome = fix_ci(DockerEnv(make_repo(tmp_path, fixed=True), config), config, must_not_run)
    assert outcome.status == NOT_REPRODUCED


def test_changing_the_test_is_rejected(tmp_path, config):
    agent = scripted(("tests/test_invoice.py", 'Decimal("0.13")', 'Decimal("0.12")'), ("tests/test_invoice.py", 'Decimal("10.13")', 'Decimal("10.12")'))
    outcome = fix_ci(DockerEnv(make_repo(tmp_path), config), config, agent)
    assert outcome.status == PROTECTED_PATH
    assert outcome.after == []


def test_wrong_fix_is_not_green_even_if_the_agent_submits(tmp_path, config):
    agent = scripted(("invoice.py", BUG, 'discounted.quantize(Decimal("0.01"), rounding="ROUND_DOWN")'))
    outcome = fix_ci(DockerEnv(make_repo(tmp_path), config), config, agent)
    assert outcome.status == NOT_GREEN and "test" in outcome.detail


def test_breaking_lint_is_not_green(tmp_path, config):
    agent = scripted(("invoice.py", BUG, GOOD_FIX), ("invoice.py", "from decimal import", "import os\nfrom decimal import"))
    outcome = fix_ci(DockerEnv(make_repo(tmp_path), config), config, agent)
    assert outcome.status == NOT_GREEN and "lint" in outcome.detail


def test_silencing_a_check_is_rejected(tmp_path, config):
    agent = scripted(("invoice.py", BUG, GOOD_FIX + "  # noqa"))
    outcome = fix_ci(DockerEnv(make_repo(tmp_path), config), config, agent)
    assert outcome.status == SUPPRESSION


def test_new_files_are_in_the_patch_and_apply_cleanly(tmp_path, config):
    def agent(task, sandbox):
        sandbox.write_file("invoice.py", sandbox.read_file("invoice.py").replace(BUG, GOOD_FIX))
        sandbox.write_file("helpers/money.py", "CENT = 1\n")
        return AgentResult(exit_reason="submitted", messages=[])

    outcome = fix_ci(DockerEnv(make_repo(tmp_path), config), config, agent)
    assert outcome.status == FIXED, outcome.detail
    assert set(outcome.changed_files) == {"invoice.py", "helpers/money.py"}


def test_bad_setup_is_reported(tmp_path, config):
    bad = replace(config, setup=("exit 3",))
    outcome = fix_ci(DockerEnv(make_repo(tmp_path), bad), bad, scripted())
    assert outcome.status == SETUP_FAILED and "exit 3" in outcome.detail.replace("退出码 3", "exit 3")


def test_snapshot_image_is_removed(tmp_path, config):
    env = DockerEnv(make_repo(tmp_path, fixed=True), config)
    fix_ci(env, config, scripted())
    assert env.snapshot is None
    images = subprocess.run(["docker", "images", "nanocoder-env", "-q"], capture_output=True, text=True).stdout.strip()
    assert images == ""
