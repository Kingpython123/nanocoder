# P2 Nano Coding Agent

从零手写的仓库级修 bug Agent（ReAct 循环 + 7 个工具 + 沙箱 + 评测）。完整计划和进展见
[doc/P2-coding-agent.md](doc/P2-coding-agent.md)。

## 目录

| 路径 | 内容 |
|---|---|
| `src/nanocoder/` | Agent 本体：`agent.py` 循环、`tools.py` 工具、`sandbox.py` 沙箱、`patch.py` 取 patch |
| `src/nanocoder/bench/` | 批量运行与评测：`python -m nanocoder.bench` |
| `benchmarks/toy/` | 20 道玩具题（测试可见，已饱和：gpt-6-luna 100%） |
| `benchmarks/hard/` | 16 道 hard v1 题（隐藏测试 + 回归陷阱；pass@1 92%，作对照），由脚本生成，不要手改 |
| `benchmarks/hard_src/` | hard 题的源头：`repos/` 两个基础仓库、`hidden/` 隐藏测试、`specs.py` bug 注入与 issue |
| `benchmarks/build_hard.py` | 从 `<suite>_src/` 生成 `<suite>/`（`--suite hard` 或 `hard2`） |
| `benchmarks/hard2/` | 12 道 hard2 题（v2：隐含约束、多处修改、根因定位；gpt-6-luna pass@1 72%），主力任务集 |
| `benchmarks/hard2_src/` | hard2 题的源头，结构同 `hard_src/` |
| `runs/` | 实验产物（git 忽略）：每次运行的 config、results.jsonl、trace、patch |
| `doc/` | 项目计划 |

依赖 `src/miniagent`（仓库根目录，LLM 客户端、工具注册、trace），包在根目录的
`pyproject.toml` 里注册，`.env` 也在仓库根目录。

## 常用命令（在仓库根目录、激活 .venv 后）

```bash
uv pip install -e ".[coding]"                                         # 安装
python -m nanocoder.bench --suite hard2 --validate                    # 校验任务（不调模型）
python -m nanocoder.bench --suite hard2 --run-id <id> --k 3 --workers 4
python -m nanocoder.bench --suite hard --tasks hard10_retry_attempts --workers 1 -v
python pri/Codingagent/benchmarks/build_hard.py --suite hard2          # 改了 hard2_src 后重新生成
```

gpt-6-luna 在 `/v1/chat/completions` 下用工具必须 `--reasoning-effort none`（默认值），并发不超过 4。
