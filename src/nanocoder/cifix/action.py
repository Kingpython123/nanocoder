"""GitHub Action 入口：评论 /nano fix-ci → 权限闸门 → 修复 → 开修复 PR 或评论说明。

安全边界（issue_comment 事件带 secret，运行在目标仓库的权限下）：
- fork 的 PR 直接拒绝，只有写权限的用户能触发；
- 主机上从不执行 PR 里的代码：git 只取文件，所有命令都在容器里；
- .nanocoder.yml 从目标分支读取，PR 改不了判定标准；
- token 通过 git 的 http.extraheader 传入，不写进 remote URL，也不进容器。
"""

from __future__ import annotations

import base64
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yaml

from .config import CIConfig, CIConfigError, parse_config
from .github import GitHub, GitHubError
from .report import render_report
from .runner import Outcome

COMMAND = re.compile(r"\s*/nano\s+fix-ci\s*\Z")
BRANCH_PREFIX = "nanocoder/fix-"
CONFIG_FILE = ".nanocoder.yml"
MAX_BODY = 60_000  # GitHub 上限 65536
ALLOWED_PERMISSIONS = {"admin", "write"}


@dataclass(frozen=True)
class Request:
    number: int
    commenter: str


def parse_event(event: dict) -> Request | None:
    """不是发给我们的事件返回 None，静默忽略。命令由这里确定性解析，不交给模型。"""
    issue, comment = event.get("issue") or {}, event.get("comment") or {}
    if event.get("action") != "created" or not issue.get("pull_request"):
        return None
    if not COMMAND.match(comment.get("body") or ""):
        return None
    return Request(issue["number"], comment["user"]["login"])


def refusal(github: GitHub, request: Request, pull: dict) -> str | None:
    """返回拒绝的原因；可以继续时返回 None。"""
    if github.permission(request.commenter) not in ALLOWED_PERMISSIONS:
        return f"@{request.commenter} does not have write access, so `/nano fix-ci` was ignored."
    head_repo = (pull["head"].get("repo") or {}).get("full_name")
    if head_repo != pull["base"]["repo"]["full_name"]:
        return "Pull requests from forks are not supported: running their code with this repository's secrets is unsafe."
    if pull["head"]["ref"].startswith(BRANCH_PREFIX):
        return "This pull request was opened by nanocoder, so it will not be fixed again."
    if pull.get("state") != "open":
        return "This pull request is not open."
    return None


def load_base_config(github: GitHub, base_ref: str) -> CIConfig:
    text = github.file_at(CONFIG_FILE, base_ref)
    if text is None:
        raise CIConfigError(f"`{CONFIG_FILE}` was not found on `{base_ref}`. Add it to the target branch first.")
    try:
        return parse_config(yaml.safe_load(text))
    except yaml.YAMLError as e:
        raise CIConfigError(f"`{CONFIG_FILE}` is not valid YAML: {e}") from e


def _git(*args: str, cwd: Path, token: str | None = None) -> None:
    command = ["git"]
    if token:
        secret = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        command += ["-c", f"http.extraheader=AUTHORIZATION: basic {secret}"]
    # 只取文件：不执行仓库带来的钩子，也不用 PR 可能带来的配置
    command += ["-c", "core.hooksPath=/dev/null", "-c", "core.autocrlf=false", *args]
    r = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        message = r.stderr.strip()
        raise RuntimeError(f"git {args[0]} failed: {message.replace(token, '***') if token else message}"[:500])


def fetch_commit(remote: str, sha: str, dest: Path, token: str | None) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", cwd=dest)
    _git("fetch", "-q", "--depth=1", remote, sha, cwd=dest, token=token)
    _git("checkout", "-q", "--detach", "FETCH_HEAD", cwd=dest)


def push_fix(repo: Path, remote: str, branch: str, patch: str, message: str, token: str | None) -> None:
    """把 patch 提交到新分支并推送。"""
    patch_file = repo.parent / "fix.patch"
    patch_file.write_text(patch, encoding="utf-8", newline="")
    _git("apply", "--binary", "--index", str(patch_file), cwd=repo)
    _git("-c", "user.name=nanocoder[bot]", "-c", "user.email=nanocoder@users.noreply.github.com", "commit", "-q", "-m", message, cwd=repo)
    _git("push", "-q", remote, f"HEAD:refs/heads/{branch}", cwd=repo, token=token)


def _body(text: str) -> str:
    """模型和日志的文字可能带 @someone，不让它们通知到真人。"""
    return text.replace("@", "@​")[:MAX_BODY]


FixRunner = Callable[[Path, CIConfig, str | None], tuple[Outcome, str]]  # (仓库, 配置, CI 日志) -> (结果, 模型名)


def handle(event: dict, github: GitHub, remote: str, token: str | None, run_fix: FixRunner) -> str:
    """处理一个事件，返回结果状态（ignored / refused / already_attempted / bad_config / 修复状态）。"""
    request = parse_event(event)
    if request is None:
        return "ignored"
    number = request.number
    pull = github.pull_request(number)
    reason = refusal(github, request, pull)
    if reason:
        github.comment(number, reason)
        return "refused"

    sha, head_ref, base_ref = pull["head"]["sha"], pull["head"]["ref"], pull["base"]["ref"]
    branch = f"{BRANCH_PREFIX}{sha[:10]}"
    if github.branch_exists(branch):
        github.comment(number, f"Commit `{sha[:10]}` was already attempted: see branch `{branch}`.")
        return "already_attempted"
    try:
        config = load_base_config(github, base_ref)
    except CIConfigError as e:
        github.comment(number, f"Cannot run `/nano fix-ci`: {e}")
        return "bad_config"

    github.comment(number, f"Working on `{sha[:10]}`. I will report back here once.")
    log = github.failed_job_logs(sha) or None
    with tempfile.TemporaryDirectory(prefix="nanocoder-action-") as tmp:
        repo = Path(tmp) / "repo"
        fetch_commit(remote, sha, repo, token)
        outcome, model = run_fix(repo, config, log)
        report = render_report(outcome, model=model)
        if not outcome.fixed:
            github.comment(number, _body(report))
            return outcome.status
        message = f"Fix failing CI for #{number}"
        push_fix(repo, remote, branch, outcome.patch, message, token)
    url = github.open_pull_request(message, branch, head_ref, _body(report + f"\n\nFixes CI on #{number}. Review before merging: passing checks do not prove the fix is right."))
    github.comment(number, f"Opened a fix: {url}")
    return outcome.status


def main_from_env(env: dict[str, str], run_fix: FixRunner) -> int:
    """Action 的入口。返回退出码：只有 nanocoder 自身出错才算失败，“没修好”已经评论说明了。"""
    event = json.loads(Path(env["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    token = env["NANOCODER_TOKEN"]
    repo = env["GITHUB_REPOSITORY"]
    server = env.get("GITHUB_SERVER_URL", "https://github.com")
    github = GitHub(token, repo)
    try:
        status = handle(event, github, f"{server}/{repo}.git", token, run_fix)
    except (GitHubError, RuntimeError, subprocess.SubprocessError) as e:
        print(f"nanocoder 出错：{str(e).replace(token, '***')}")
        issue = (event.get("issue") or {}).get("number")
        if issue and parse_event(event):
            try:
                github.comment(issue, "nanocoder failed with an internal error. See the workflow log.")
            except GitHubError:
                pass
        return 1
    print(f"结果：{status}")
    return 0
