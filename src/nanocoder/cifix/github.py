"""GitHub REST API 的最小封装，只用标准库。token 只放在请求头里，不进 URL、日志和容器。"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from typing import Any

API = "https://api.github.com"


class GitHubError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"GitHub API {status}: {message}")
        self.status = status


class GitHub:
    def __init__(self, token: str, repo: str, api: str = API):
        self.token, self.repo, self.api = token, repo, api.rstrip("/")

    def _request(self, method: str, path: str, body: dict | None = None, raw: bool = False) -> Any:
        url = f"{self.api}/repos/{self.repo}/{path}"
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header("Authorization", f"Bearer {self.token}")
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        request.add_header("User-Agent", "nanocoder")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = response.read()
        except urllib.error.HTTPError as e:
            raise GitHubError(e.code, e.read().decode("utf-8", "replace")[:300]) from e
        if raw:
            return payload.decode("utf-8", "replace")
        return json.loads(payload) if payload else None

    def pull_request(self, number: int) -> dict:
        return self._request("GET", f"pulls/{number}")

    def permission(self, user: str) -> str:
        """admin / write / read / none。"""
        return self._request("GET", f"collaborators/{user}/permission")["permission"]

    def file_at(self, path: str, ref: str) -> str | None:
        try:
            data = self._request("GET", f"contents/{path}?ref={ref}")
        except GitHubError as e:
            if e.status == 404:
                return None
            raise
        return base64.b64decode(data["content"]).decode("utf-8")

    def branch_exists(self, branch: str) -> bool:
        try:
            self._request("GET", f"git/ref/heads/{branch}")
            return True
        except GitHubError as e:
            if e.status == 404:
                return False
            raise

    def failed_job_logs(self, sha: str, limit: int = 3) -> str:
        """这个提交上失败 job 的日志。日志是参考信息，取不到不影响修复（真正的依据是本地复现）。"""
        try:
            runs = self._request("GET", f"actions/runs?head_sha={sha}&status=failure&per_page=10")["workflow_runs"]
            parts: list[str] = []
            for run in runs:
                for job in self._request("GET", f"actions/runs/{run['id']}/jobs?filter=latest")["jobs"]:
                    if job["conclusion"] == "failure" and len(parts) < limit:
                        log = self._request("GET", f"actions/jobs/{job['id']}/logs", raw=True)
                        parts.append(f"=== job: {job['name']} ===\n{log}")
            return "\n\n".join(parts)
        except (GitHubError, urllib.error.URLError, TimeoutError):
            return ""

    def comment(self, number: int, body: str) -> None:
        self._request("POST", f"issues/{number}/comments", {"body": body})

    def open_pull_request(self, title: str, head: str, base: str, body: str) -> str:
        return self._request("POST", "pulls", {"title": title, "head": head, "base": base, "body": body})["html_url"]
