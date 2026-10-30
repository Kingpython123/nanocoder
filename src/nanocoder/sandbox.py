"""沙箱：Agent 的所有命令和文件读写都经过这里。

M0 只有 LocalSandbox：把仓库复制到临时目录，用 Git Bash 执行命令。
它只隔离了"工作目录"，没有隔离网络、进程和宿主机文件，只能跑自己写的玩具任务。
M1 会加 DockerSandbox，对外接口保持不变，工具和 agent loop 不用改。
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


class SandboxError(Exception):
    """沙箱自身出错（不是命令执行失败）。"""


@dataclass
class CommandResult:
    exit_code: int  # 超时时为 -1
    output: str  # stdout 和 stderr 合并
    timed_out: bool = False


class Sandbox:
    """沙箱接口。路径一律是相对仓库根目录的 POSIX 风格路径。"""

    def run(self, command: str, timeout: float = 120) -> CommandResult:
        raise NotImplementedError

    def read_file(self, path: str) -> str:
        raise NotImplementedError

    def write_file(self, path: str, content: str) -> None:
        raise NotImplementedError

    def exists(self, path: str) -> bool:
        raise NotImplementedError

    def is_dir(self, path: str) -> bool:
        raise NotImplementedError

    def close(self) -> None:
        pass

    def __enter__(self) -> "Sandbox":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def find_bash() -> str:
    """找 Git Bash。Windows 上不能直接用 PATH 里的 bash：它可能是 WSL 的 bash.exe。"""
    if env := os.getenv("NANOCODER_BASH"):
        return env
    if sys.platform != "win32":
        found = shutil.which("bash")
        if found:
            return found
        raise SandboxError("找不到 bash")
    git = shutil.which("git")
    if git:
        for parent in Path(git).resolve().parents:
            for candidate in (parent / "usr" / "bin" / "bash.exe", parent / "bin" / "bash.exe"):
                if candidate.exists():
                    return str(candidate)
    raise SandboxError("找不到 Git Bash。请安装 Git for Windows，或设置环境变量 NANOCODER_BASH 指向 bash.exe")


class LocalSandbox(Sandbox):
    """在临时目录里的仓库副本上工作。"""

    def __init__(self, source_repo: str | Path, init_git: bool = True):
        self._tmp = Path(tempfile.mkdtemp(prefix="nanocoder-"))
        self.root = self._tmp / "repo"
        shutil.copytree(source_repo, self.root, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
        self.bash = find_bash()
        # 让命令里的 python / pytest 指向当前虚拟环境
        scripts = Path(sys.executable).parent
        self.env = {
            **os.environ,
            "PATH": str(scripts) + os.pathsep + os.environ.get("PATH", ""),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "utf-8",
            "GIT_AUTHOR_NAME": "nanocoder",
            "GIT_AUTHOR_EMAIL": "nanocoder@example.com",
            "GIT_COMMITTER_NAME": "nanocoder",
            "GIT_COMMITTER_EMAIL": "nanocoder@example.com",
        }
        if init_git:
            # 和 SWE-bench 镜像一样，让仓库处于"干净的 git 工作区"，patch 用 git diff 生成
            # autocrlf 关掉：否则 Git for Windows 会在 diff 里混入换行符变化
            r = self.run(
                "git init -q && git config core.autocrlf false && git add -A && git commit -q -m init",
                timeout=60,
            )
            if r.exit_code != 0:
                raise SandboxError(f"初始化 git 失败：{r.output}")

    def _resolve(self, path: str) -> Path:
        rel = PurePosixPath(path.replace("\\", "/"))
        if rel.is_absolute():
            # 这两条错误会回传给模型，用英文
            raise SandboxError(f"use a path relative to the repository root, got absolute path {path!r}")
        full = (self.root / rel).resolve()
        if full != self.root.resolve() and self.root.resolve() not in full.parents:
            raise SandboxError(f"path {path!r} is outside the repository; access denied")
        return full

    def run(self, command: str, timeout: float = 120) -> CommandResult:
        kwargs: dict = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        proc = subprocess.Popen(
            [self.bash, "-c", command],
            cwd=self.root,
            env=self.env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            **kwargs,
        )
        try:
            out, _ = proc.communicate(timeout=timeout)
            return CommandResult(proc.returncode, _decode(out))
        except subprocess.TimeoutExpired:
            _kill_tree(proc)
            out, _ = proc.communicate()
            return CommandResult(-1, _decode(out), timed_out=True)

    def read_file(self, path: str) -> str:
        return self._resolve(path).read_text(encoding="utf-8", errors="replace")

    def write_file(self, path: str, content: str) -> None:
        full = self._resolve(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        # newline="" 保留模型给的换行符，不让 Windows 自动改成 \r\n
        with open(full, "w", encoding="utf-8", newline="") as f:
            f.write(content)

    def exists(self, path: str) -> bool:
        return self._resolve(path).exists()

    def is_dir(self, path: str) -> bool:
        return self._resolve(path).is_dir()

    def close(self) -> None:
        # .git/objects 里的文件是只读的，Windows 上要先去掉只读属性才能删
        def _force(func, path, _exc):  # type: ignore[no-untyped-def]
            try:
                os.chmod(path, 0o700)
                func(path)
            except OSError:
                pass

        shutil.rmtree(self._tmp, onerror=_force)


def _decode(data: bytes | None) -> str:
    return (data or b"").decode("utf-8", errors="replace")


def _kill_tree(proc: subprocess.Popen) -> None:
    """超时后杀掉整个进程树，否则 bash 起的 python 子进程会残留。"""
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
