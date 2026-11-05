"""M1：Docker 沙箱。接口和 LocalSandbox 完全一样，工具和 agent loop 不用改。

每个任务起一个长期运行的容器（`sleep infinity`），命令用 `docker exec` 在里面跑：
- 断网（--network none）、限内存 / CPU / 进程数，agent 动不到宿主机；
- 超时由容器内的 `timeout -s KILL` 负责，杀掉整个命令；宿主机侧再留一个兜底超时；
- 文件读写也走 docker exec（cat / 管道写入），路径必须在工作目录内。

SWE-bench 的实例镜像（swebench/sweb.eval.x86_64.<id>）里仓库在 /testbed，依赖装在 conda 环境
testbed 里，所以 SWE-bench 用 `DockerSandbox.for_swebench(image)`，它会在每条命令前激活环境。

需要在能用 docker 的环境里运行（本项目用 WSL2 里的 Docker Engine）。
"""

from __future__ import annotations

import posixpath
import shlex
import subprocess
import uuid

from .sandbox import CommandResult, Sandbox, SandboxError

SWEBENCH_PREFIX = "source /opt/miniconda3/bin/activate testbed && "


class DockerSandbox(Sandbox):
    def __init__(
        self,
        image: str,
        workdir: str = "/testbed",
        shell_prefix: str = "",
        memory: str = "4g",
        cpus: float = 2.0,
        network: str = "none",
        docker: str = "docker",
    ):
        self.image = image
        self.workdir = workdir
        self.shell_prefix = shell_prefix
        self.docker = docker
        self.name = f"nanocoder-{uuid.uuid4().hex[:12]}"
        cmd = [
            docker, "run", "-d", "--rm",
            "--name", self.name,
            "--network", network,
            "--memory", memory,
            "--cpus", str(cpus),
            "--pids-limit", "512",
            "-w", workdir,
            "-e", "PYTHONDONTWRITEBYTECODE=1",
            "-e", "PYTHONIOENCODING=utf-8",
            "--entrypoint", "sleep",
            image, "infinity",
        ]  # fmt: skip
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            raise SandboxError(f"启动容器失败（镜像 {image}）：{r.stderr.strip()[:500]}")

    @classmethod
    def for_swebench(cls, image: str, **kwargs) -> "DockerSandbox":
        return cls(image, workdir="/testbed", shell_prefix=SWEBENCH_PREFIX, **kwargs)

    # ------------------------------------------------------------------ helpers

    def _exec(self, args: list[str], timeout: float, stdin: bytes | None = None) -> subprocess.CompletedProcess:
        cmd = [self.docker, "exec", *(["-i"] if stdin is not None else []), "-w", self.workdir, self.name, *args]
        return subprocess.run(cmd, input=stdin, capture_output=True, timeout=timeout)

    def _path(self, path: str) -> str:
        """相对仓库根目录的路径 -> 容器内绝对路径；拒绝绝对路径和越界路径（错误信息回传给模型，用英文）。"""
        rel = path.replace("\\", "/")
        if rel.startswith("/"):
            raise SandboxError(f"use a path relative to the repository root, got absolute path {path!r}")
        full = posixpath.normpath(posixpath.join(self.workdir, rel))
        if full != self.workdir and not full.startswith(self.workdir.rstrip("/") + "/"):
            raise SandboxError(f"path {path!r} is outside the repository; access denied")
        return full

    # ------------------------------------------------------------------ Sandbox

    def run(self, command: str, timeout: float = 120) -> CommandResult:
        # 容器内用 timeout -s KILL 杀命令；exit 137 = 被 KILL
        inner = f"timeout -s KILL {int(timeout)} bash -c {shlex.quote(self.shell_prefix + command)}"
        try:
            r = self._exec(["bash", "-c", inner + " 2>&1"], timeout=timeout + 30)
        except subprocess.TimeoutExpired:
            return CommandResult(-1, "", timed_out=True)
        output = r.stdout.decode("utf-8", errors="replace") + r.stderr.decode("utf-8", errors="replace")
        if r.returncode == 137:
            return CommandResult(-1, output, timed_out=True)
        return CommandResult(r.returncode, output)

    def read_file(self, path: str) -> str:
        r = self._exec(["cat", "--", self._path(path)], timeout=60)
        if r.returncode != 0:
            raise SandboxError(r.stderr.decode("utf-8", errors="replace").strip() or f"cannot read {path!r}")
        return r.stdout.decode("utf-8", errors="replace")

    def write_file(self, path: str, content: str) -> None:
        full = self._path(path)
        script = f"mkdir -p {shlex.quote(posixpath.dirname(full))} && cat > {shlex.quote(full)}"
        r = self._exec(["sh", "-c", script], timeout=60, stdin=content.encode("utf-8"))
        if r.returncode != 0:
            raise SandboxError(r.stderr.decode("utf-8", errors="replace").strip() or f"cannot write {path!r}")

    def exists(self, path: str) -> bool:
        return self._exec(["test", "-e", self._path(path)], timeout=30).returncode == 0

    def is_dir(self, path: str) -> bool:
        return self._exec(["test", "-d", self._path(path)], timeout=30).returncode == 0

    def put_tar(self, data: bytes) -> None:
        """把 tar 包解到工作目录。"""
        r = self._exec(["tar", "-xf", "-", "-C", self.workdir], timeout=300, stdin=data)
        if r.returncode != 0:
            raise SandboxError(f"解包失败：{r.stderr.decode('utf-8', errors='replace').strip()[:500]}")

    def commit(self, tag: str) -> None:
        """把容器当前状态保存成镜像，之后可以直接从它启动。"""
        r = subprocess.run([self.docker, "commit", self.name, tag], capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            raise SandboxError(f"docker commit 失败：{r.stderr.strip()[:500]}")

    def close(self) -> None:
        subprocess.run([self.docker, "rm", "-f", self.name], capture_output=True, timeout=120)
