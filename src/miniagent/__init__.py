"""miniagent：一个用来学习 agent 原理的最小实现。

模块一览：
- config        读取 .env 配置
- llm           OpenAI 兼容接口的薄封装
- tools         @tool 装饰器 + 工具注册中心
- builtin_tools 内置示例工具
- trace         每一步的追踪日志
- agent         你的练习：实现 Agent.run()
"""

__version__ = "0.1.0"
