"""GitHub Action 流程的测试：假的 GitHub API + 本地真实的 git 远端。不需要 docker，也不调模型。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from nanocoder.agent import AgentResult
from nanocoder.cifix.action import BRANCH_PREFIX, handle, main_from_env, parse_event
from nanocoder.cifix.github import GitHubError
from nanocoder.cifix.runner import FIXED, NOT_GREEN, Outcome

CONFIG = "image: python:3.12\nchecks:\n  - {name: test, command: pytest}\n"
PATCH = "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-a = 1\n+a = 2\n"
EVENT = {
    "action": "created",
    "issue": {"number": 7, "pull_request": {"url": "x"}},
    "comment": {"body": "/nano fix-ci", "user": {"login": "alice"}},
}


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "core.autocrlf=false", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def remote(tmp_path):
    """一个带 feature 分支的裸仓库，返回 (路径, feature 的 sha)。"""
    bare = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(bare))
    work = tmp_path / "work"
    work.mkdir()
    git(work, "init", "-q")
    (work / "app.py").write_bytes(b"a = 1\n")
    git(work, "add", "-A")
    git(work, "-c", "user.name=t", "-c", "user.email=t@e.com", "commit", "-q", "-m", "init")
    git(work, "push", "-q", str(bare), "HEAD:refs/heads/feature")
    return str(bare), git(work, "rev-parse", "HEAD")


class FakeGitHub:
    def __init__(self, sha="a" * 40, permission="write", head_repo="o/r", ref="feature", config=CONFIG, state="open", existing=False):
        self.pull = {
            "state": state,
            "head": {"sha": sha, "ref": ref, "repo": {"full_name": head_repo} if head_repo else None},
            "base": {"ref": "main", "repo": {"full_name": "o/r"}},
        }
        self.perm, self.config, self.existing = permission, config, existing
        self.comments: list[str] = []
        self.opened: list[dict] = []
        self.config_refs: list[str] = []

    def pull_request(self, number):
        return self.pull

    def permission(self, user):
        return self.perm

    def file_at(self, path, ref):
        self.config_refs.append(ref)
        return self.config

    def branch_exists(self, branch):
        return self.existing

    def failed_job_logs(self, sha):
        return "ci log"

    def comment(self, number, body):
        self.comments.append(body)

    def open_pull_request(self, title, head, base, body):
        self.opened.append({"title": title, "head": head, "base": base, "body": body})
        return "https://example.com/pull/8"


def fixed(repo, config, log):
    return Outcome(FIXED, patch=PATCH, changed_files=["app.py"], agent=AgentResult(exit_reason="submitted")), "m"


def must_not_run(repo, config, log):
    raise AssertionError("不应该开始修复")


# ---------------------------------------------------------------- 事件解析


@pytest.mark.parametrize(
    "change",
    [
        {"action": "edited"},
        {"action": "deleted"},
        {"issue": {"number": 7}},  # 普通 issue，不是 PR
        {"comment": {"body": "please /nano fix-ci now", "user": {"login": "a"}}},
        {"comment": {"body": "/nano fix-ci; rm -rf /", "user": {"login": "a"}}},
        {"comment": {"body": "/nano review", "user": {"login": "a"}}},
        {"comment": {"body": None, "user": {"login": "a"}}},
    ],
)
def test_other_events_are_ignored(change):
    assert parse_event({**EVENT, **change}) is None


@pytest.mark.parametrize("body", ["/nano fix-ci", "  /nano   fix-ci \n"])
def test_command_is_recognized(body):
    request = parse_event({**EVENT, "comment": {"body": body, "user": {"login": "alice"}}})
    assert request.number == 7 and request.commenter == "alice"


def test_ignored_event_does_nothing():
    github = FakeGitHub()
    assert handle({**EVENT, "action": "edited"}, github, "x", None, must_not_run) == "ignored"
    assert github.comments == []


# ---------------------------------------------------------------- 权限闸门


@pytest.mark.parametrize("permission", ["read", "none"])
def test_no_write_access_is_refused(permission):
    github = FakeGitHub(permission=permission)
    assert handle(EVENT, github, "x", None, must_not_run) == "refused"
    assert "write access" in github.comments[0]


@pytest.mark.parametrize("head_repo", ["someone/fork", None])
def test_forks_are_refused(head_repo):
    github = FakeGitHub(head_repo=head_repo)
    assert handle(EVENT, github, "x", None, must_not_run) == "refused"
    assert "forks" in github.comments[0]


def test_own_fix_branch_is_not_fixed_again():
    github = FakeGitHub(ref=f"{BRANCH_PREFIX}abc")
    assert handle(EVENT, github, "x", None, must_not_run) == "refused"


def test_closed_pr_is_refused():
    assert handle(EVENT, FakeGitHub(state="closed"), "x", None, must_not_run) == "refused"


def test_same_commit_is_not_attempted_twice():
    github = FakeGitHub(existing=True)
    assert handle(EVENT, github, "x", None, must_not_run) == "already_attempted"


# ---------------------------------------------------------------- 配置


def test_config_comes_from_the_target_branch(remote):
    bare, sha = remote
    github = FakeGitHub(sha=sha)
    handle(EVENT, github, bare, None, fixed)
    assert github.config_refs == ["main"]


@pytest.mark.parametrize("config", [None, "image: [", "image: x\n"])
def test_bad_config_is_reported_without_running(config):
    github = FakeGitHub(config=config)
    assert handle(EVENT, github, "x", None, must_not_run) == "bad_config"
    assert "Cannot run" in github.comments[0]


# ---------------------------------------------------------------- 交付


def test_fixed_pushes_a_branch_and_opens_a_pr_against_the_failing_branch(remote):
    bare, sha = remote
    github = FakeGitHub(sha=sha)
    assert handle(EVENT, github, bare, None, fixed) == FIXED
    branch = f"{BRANCH_PREFIX}{sha[:10]}"
    assert github.opened[0]["head"] == branch and github.opened[0]["base"] == "feature"
    assert "https://example.com/pull/8" in github.comments[-1]
    assert git(Path(bare), "show", f"{branch}:app.py") == "a = 2"
    assert git(Path(bare), "log", "-1", "--format=%an", branch) == "nanocoder[bot]"
    assert git(Path(bare), "rev-parse", f"{branch}~1") == sha
    assert git(Path(bare), "rev-parse", "feature") == sha  # 原分支不动


def test_not_fixed_only_comments_and_pushes_nothing(remote):
    bare, sha = remote
    github = FakeGitHub(sha=sha)

    def not_green(repo, config, log):
        return Outcome(NOT_GREEN, detail="Still failing", patch=PATCH), "m"

    assert handle(EVENT, github, bare, None, not_green) == NOT_GREEN
    assert github.opened == []
    assert "Still failing" in github.comments[-1]
    assert git(Path(bare), "for-each-ref", "--format=%(refname:short)") == "feature"


def test_the_commit_being_fixed_and_the_log_reach_the_runner(remote):
    bare, sha = remote
    seen = {}

    def spy(repo, config, log):
        seen.update(sha=git(repo, "rev-parse", "HEAD"), log=log, image=config.image)
        return Outcome(NOT_GREEN, detail="x"), "m"

    handle(EVENT, FakeGitHub(sha=sha), bare, None, spy)
    assert seen == {"sha": sha, "log": "ci log", "image": "python:3.12"}


def test_mentions_in_reports_do_not_notify_people(remote):
    bare, sha = remote
    github = FakeGitHub(sha=sha)

    def noisy(repo, config, log):
        return Outcome(NOT_GREEN, detail="ask @someone"), "m"

    handle(EVENT, github, bare, None, noisy)
    assert "@someone" not in github.comments[-1]


# ---------------------------------------------------------------- 入口


def test_main_hides_the_token_when_github_fails(tmp_path, capsys, monkeypatch):
    event = tmp_path / "event.json"
    event.write_text(json.dumps(EVENT), encoding="utf-8")

    class Broken:
        def __init__(self, *args):
            pass

        def pull_request(self, number):
            raise GitHubError(500, "boom secret-token")

        def comment(self, number, body):
            raise GitHubError(500, "boom")

    monkeypatch.setattr("nanocoder.cifix.action.GitHub", Broken)
    code = main_from_env({"GITHUB_EVENT_PATH": str(event), "NANOCODER_TOKEN": "secret-token", "GITHUB_REPOSITORY": "o/r"}, must_not_run)
    assert code == 1
    assert "secret-token" not in capsys.readouterr().out
