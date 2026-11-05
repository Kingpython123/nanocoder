"""Docker 环境：联网构建一次，之后每次都从快照启动断网容器。

- 只复制 git 里已提交的内容（git archive），工作区的 .env 之类不会进容器；
- 构建容器联网执行 setup，然后 docker commit 成快照；
- agent 和判定各用一个从快照启动的新容器，断网，不传任何 key 或 token。

git 基线在 setup 之后提交，这样 setup 产生的文件不会混进 agent 的 diff。
"""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

from ..docker_sandbox import DockerSandbox
from ..sandbox import SandboxError
from .config import CIConfig

WORKDIR = "/workspace"
_INIT_GIT = (
    "git init -q && git config core.autocrlf false && git add -A && "
    "git -c user.name=nanocoder -c user.email=nanocoder@example.com commit -q --allow-empty -m baseline"
)


class EnvSetupError(Exception):
    """环境没搭起来，错误信息给用户看。"""


class DockerEnv:
    def __init__(self, repo: str | Path, config: CIConfig, docker: str = "docker"):
        self.repo = Path(repo)
        self.config = config
        self.docker = docker
        self.snapshot: str | None = None

    def prepare(self) -> None:
        cfg, limits = self.config, self.config.limits
        archive = subprocess.run(["git", "-C", str(self.repo), "archive", "HEAD"], capture_output=True, timeout=300)
        if archive.returncode != 0:
            raise EnvSetupError(f"git archive 失败：{archive.stderr.decode('utf-8', 'replace')[:500]}")
        self._pull(cfg.image)
        try:
            builder = DockerSandbox(cfg.image, workdir=WORKDIR, network="bridge", memory=limits.memory, cpus=limits.cpus, docker=self.docker)
        except SandboxError as e:
            raise EnvSetupError(str(e)) from e
        try:
            builder.put_tar(archive.stdout)
            for command in cfg.setup:
                r = builder.run(command, timeout=limits.setup_timeout)
                if r.exit_code != 0 or r.timed_out:
                    state = "超时" if r.timed_out else f"退出码 {r.exit_code}"
                    raise EnvSetupError(f"setup 命令失败（{state}）：{command}\n{r.output[-2000:]}")
            r = builder.run(_INIT_GIT, timeout=120)
            if r.exit_code != 0:
                raise EnvSetupError(f"初始化 git 基线失败（镜像里要有 git，可以在 setup 里安装）：\n{r.output[-1000:]}")
            tag = f"nanocoder-env:{uuid.uuid4().hex[:12]}"
            builder.commit(tag)
            self.snapshot = tag
        finally:
            builder.close()

    def open(self) -> DockerSandbox:
        """从快照启动一个新的断网容器。"""
        if self.snapshot is None:
            raise RuntimeError("先调用 prepare()")
        limits = self.config.limits
        return DockerSandbox(self.snapshot, workdir=WORKDIR, network="none", memory=limits.memory, cpus=limits.cpus, docker=self.docker)

    def close(self) -> None:
        if self.snapshot:
            subprocess.run([self.docker, "rmi", "-f", self.snapshot], capture_output=True, timeout=120)
            self.snapshot = None

    def _pull(self, image: str) -> None:
        if subprocess.run([self.docker, "image", "inspect", image], capture_output=True, timeout=60).returncode == 0:
            return
        r = subprocess.run([self.docker, "pull", "-q", image], capture_output=True, text=True, timeout=1800)
        if r.returncode != 0:
            raise EnvSetupError(f"拉取镜像失败：{image}：{r.stderr.strip()[:500]}")
