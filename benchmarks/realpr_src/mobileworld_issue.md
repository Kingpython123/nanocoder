# Five English MCP tasks are missing the lang-en tag

Five English tasks in the MCP set have no `lang-*` tag. Every other registered task has exactly one (`lang-en` or `lang-cn`).

| Task | File |
|---|---|
| `PlanDrivingRouteSmsTask` | `messages/plan_driving_route_sms.py` |
| `ExtractBenchmarkComparisonEmailTask` | `work/extract_benchmark_comparison_email.py` |
| `ExtractMultilingualScoresEmailTask` | `work/extract_multilingual_scores_email.py` |
| `ExtractPipelineStagesEmailTask` | `work/extract_pipeline_stages_email.py` |
| `ExtractTrajectoryEnvironmentsEmailTask` | `work/extract_trajectory_environments_email.py` |

All five have `task_tags = {"agent-mcp"}` and English goals. The sibling route tasks (`PlanTaxiRouteSmsTask`, `PlanCyclingRouteSmsTask`, `PlanCommuteRouteSmsTask`) are tagged `{"agent-mcp", "lang-en"}`.

**Effect:** filtering by `lang-en` in the log viewer (`tag_filter` in `core/log_viewer/routes.py`) skips these tasks, and any per-language breakdown is off by five.

**Reproduce:**

```python
from mobile_world.tasks.registry import TaskRegistry
r = TaskRegistry()
print([n for n in r.list_tasks()
       if not any(t.startswith("lang-") for t in r.get_task(n).task_tags)])
```

Current language counts are `lang-en` 155, `lang-cn` 41 and untagged 5. With the fix they are `lang-en` 160 and `lang-cn` 41.

I'll open a PR that adds `lang-en` to these five tasks, with a test that every task has exactly one language tag.

