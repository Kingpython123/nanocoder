# (mobile agent v3.5):parse_action 在模型输出为空或缺少 <tool_call> 时抛出 IndexError

### 问题描述

在 `run_gui_owl_1_5_for_mobile.py` 中，当模型某一步未返回内容或返回内容不包含 `<tool_call>` 时，`parse_action` 会抛出 `IndexError: list index out of range`，导致程序崩溃。

### 复现步骤

1. 运行 `uv run run_gui_owl_1_5_for_mobile.py`
2. 在某一轮（例如 STEP 1）模型返回空输出或非 `<tool_call>` 格式
3. 程序在 `parse_action` 中崩溃

### 错误信息

```
Traceback (most recent call last):
  File ".../run_gui_owl_1_5_for_mobile.py", line 67, in parse_action
    tool_call_block = output_text.split("<tool_call>\n")[1]
                      ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^
IndexError: list index out of range

During handling of the above exception, another exception occurred:
...
ValueError: Failed to parse action from model output: list index out of range
```

使用的模型是百炼平台提供的qwen3.5-plus model
