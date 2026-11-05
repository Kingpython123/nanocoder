# nanocoder

从零手写的仓库级修 bug Agent（ReAct 循环 + 7 个工具 + 沙箱 + 评测）。下一步是做成自托管的仓库 AI 队友，方向见
[doc/产品化头脑风暴.md](doc/产品化头脑风暴.md)。完整计划和进展见 [doc/P2-coding-agent.md](doc/P2-coding-agent.md)，
当前状态的梳理见 [doc/P2-progress.html](doc/P2-progress.html)。

这个仓库于 2026-11-05 从 agent-learning 的 `pri/Codingagent/` 拆出，保留了提交历史。

## 目录

| 路径 | 内容 |
|---|---|
| `src/nanocoder/` | Agent 本体：`agent.py` 循环、`tools.py` 工具、`sandbox.py` / `docker_sandbox.py` 沙箱、`responses_llm.py` Responses API、`patch.py` 取 patch |
| `src/nanocoder/bench/` | 批量运行与评测：`python -m nanocoder.bench`；SWE-bench：`python -m nanocoder.bench.swebench_run` |
| `src/miniagent/` | LLM 客户端、工具注册、trace。从 agent-learning 复制而来，之后在这里独立维护 |
| `benchmarks/toy/` | 20 道玩具题（测试可见，已饱和：gpt-6-luna 100%） |
| `benchmarks/hard/` | 16 道 hard v1 题（隐藏测试 + 回归陷阱；pass@1 92%，作对照），由脚本生成，不要手改 |
| `benchmarks/hard_src/` | hard 题的源头：`repos/` 两个基础仓库、`hidden/` 隐藏测试、`specs.py` bug 注入与 issue |
| `benchmarks/build_hard.py` | 从 `<suite>_src/` 生成 `<suite>/`（`--suite hard` 或 `hard2`） |
| `benchmarks/hard2/` | 12 道 hard2 题（隐含约束、多处修改、根因定位；基线 pass@1 72%），消融实验都在这里做 |
| `benchmarks/hard2_src/` | hard2 题的源头，结构同 `hard_src/` |
| `benchmarks/swebench/` | SWE-bench Verified 50 题子集（按仓库分层，seed=42） |
| `benchmarks/build_realpr.py` | 把已合并的真实 PR 做成回放任务，`realpr_src/` 是 issue 原文 |
| `runs/` | 实验产物（git 忽略）：每次运行的 config、results.jsonl、trace、patch |
| `doc/` | 项目计划、进度梳理、产品化头脑风暴 |

## 常用命令（在仓库根目录、激活 .venv 后）

配置：`Copy-Item .env.example .env`，然后填写中转站地址、key 和模型名。

```bash
uv pip install -e ".[coding]"                                         # 安装
python -m nanocoder.bench --suite hard2 --validate                    # 校验任务（不调模型）
python -m nanocoder.bench --suite hard2 --run-id <id> --k 3 --workers 4 --api responses --reasoning-effort high --prompt v2_spec
python -m nanocoder.bench --suite hard --tasks hard10_retry_attempts --workers 1 -v
python benchmarks/build_hard.py --suite hard2                         # 改了 hard2_src 后重新生成
```

SWE-bench 需要 Linux（WSL2）和 Docker，先 `uv pip install -e ".[swebench]"`：

```bash
python -m nanocoder.bench.swebench_run --run-id <id> --api responses --reasoning-effort high --prompt v2_spec --workers 1 --batch 6
```

中断后加 `--retry-errors` 续跑。花钱的实验开跑前先估 token。
