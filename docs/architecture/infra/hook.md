# MiniCode 架构设计文档 - Hook 通用生命周期系统

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. 设计目标

**Hook 通用生命周期系统** - 为 Agent、Session、Evolution 等模块提供统一的生命周期扩展机制。

> Hook 从 tool/ 移至 infra/hook/，作为通用生命周期机制。

### 1.1 为什么需要通用 Hook

| 问题 | 解决方案 |
|------|----------|
| 工具执行前后的日志、监控 | 工具 Hook |
| Agent 启动/结束的日志 | Agent Hook |
| Session 开始/结束的记录 | Session Hook |
| 统一机制 | 抽象为通用 Hook 系统 |

### 1.2 设计原则

| 原则 | 说明 | 原因 |
|------|------|------|
| **双轨制** | 内置 Hook + 用户配置 | 灵活性 |
| **自动注册** | @auto_hook 装饰器 | 简化使用 |
| **优先级执行** | 按优先级排序 | 控制顺序 |
| **错误隔离** | Hook 失败不影响主流程 | 可靠性 |

---

## 2. 模块结构

```
infra/hook/
├── __init__.py              # 导出公共类型
├── registry.py              # Hook 注册表 + @auto_hook 装饰器
├── types.py                 # Hook 类型定义（HookType、HookContext、Hook）
├── config.py                # 用户配置加载（.hooks.json）
└── builtin/                 # 内置 Hook（@auto_hook 自动注册）
    ├── logging.py           # 日志 Hook（priority=10）
    ├── metrics.py           # 指标 Hook（priority=20）
    └── permission.py        # 权限 Hook（priority=100）
```

---

## 3. 双轨制设计

Hook 支持两种注册方式：**内置 Hook** 和 **用户配置 Hook**。

| 类型 | 注册方式 | 执行方式 | 示例 |
|------|----------|----------|------|
| **内置 Hook** | `@auto_hook` 装饰器 | Python 函数 | logging、metrics、permission |
| **用户配置 Hook** | `.minicode/hooks.json` | 外部命令 | 用户自定义验证 |

### 3.1 内置 Hook

开发者使用 `@auto_hook` 装饰器，启动时自动注册。

```python
# infra/hook/builtin/permission.py

@auto_hook(HookType.TOOL_BEFORE, priority=HookPriority.PERMISSION)
def check_permission(ctx: HookContext) -> None:
    """权限检查 Hook"""
    tool_name = ctx.data.get("tool_name", "")
    args = ctx.data.get("args", {})

    if is_dangerous_tool(tool_name, args):
        if not confirm_dangerous_operation(tool_name, args):
            raise PermissionDenied(f"Tool {tool_name} requires confirmation")
```

### 3.2 用户配置 Hook

用户通过配置文件指定外部命令，支持任意语言。

```json
// .minicode/hooks.json
{
    "hooks": {
        "PreToolUse": [
            {
                "matcher": "bash",
                "command": "python verify_bash.py"
            }
        ],
        "PostToolUse": [
            {
                "matcher": "*",
                "command": "echo 'Tool used: {tool_name}'"
            }
        ]
    }
}
```

**退出码协议**：

| 退出码 | 行为 | 说明 |
|--------|------|------|
| 0 | 继续执行 | Hook 验证通过 |
| 1 | 拦截操作 | Hook 拒绝执行 |
| 2 | 注入上下文 | Hook 提供额外信息 |

---

## 4. Hook 类型定义

### 4.1 优先级

```python
class HookPriority:
    """Hook 优先级常量 - 数字越大越先执行"""

    # 系统基础设施（0-99）
    LOGGING = 10        # 日志记录
    METRICS = 20       # 指标收集
    TRACING = 30       # 链路追踪

    # 核心业务（100-199）
    PERMISSION = 100   # 权限检查
    VALIDATION = 110    # 参数验证
    SECURITY = 120     # 安全检查

    # 业务逻辑（200-299）
    CACHE = 200        # 缓存处理
    TRANSFORM = 210     # 数据转换

    # 用户插件（300+）
    USER_HOOK = 300    # 用户自定义
    PLUGIN = 400       # 插件钩子
```

### 4.2 Hook 类型

```python
class HookType(Enum):
    """Hook 类型"""
    # 工具执行 Hook
    TOOL_BEFORE = "tool.before"
    TOOL_AFTER = "tool.after"
    TOOL_ERROR = "tool.error"

    # Agent 生命周期 Hook
    AGENT_START = "agent.start"
    AGENT_END = "agent.end"
    AGENT_ERROR = "agent.error"

    # Session 生命周期 Hook
    SESSION_START = "session.start"
    SESSION_END = "session.end"

    # Evolution 生命周期 Hook
    EVOLUTION_START = "evolution.start"
    EVOLUTION_COMPLETE = "evolution.complete"
```

### 4.3 Hook 上下文

```python
@dataclass
class HookContext:
    """Hook 上下文"""
    hook_type: HookType
    module: str                          # 模块名（tool/agent/session）
    event: str                          # 事件名
    data: dict                           # 事件数据
    timestamp: float


@dataclass
class Hook:
    """Hook 定义"""
    name: str
    hook_type: HookType
    handler: Callable[[HookContext], Any]
    priority: int = HookPriority.LOGGING  # 默认优先级
    enabled: bool = True

    def __post_init__(self):
        @wraps(self.handler)
        def wrapper(ctx: HookContext) -> Any:
            if self.enabled:
                return self.handler(ctx)
        self._handler = wrapper
```

---

## 5. 自动注册机制

### 5.1 @auto_hook 装饰器

**问题**：手动 `hooks.register(Hook(...))` 太繁琐

**解决方案**：装饰器自动注册

```python
# infra/hook/registry.py - 自动注册机制

from functools import wraps
from typing import Callable, Optional

# 全局注册表（单例）
_global_hook_registry: Optional["HookRegistry"] = None

def get_hook_registry() -> "HookRegistry":
    global _global_hook_registry
    if _global_hook_registry is None:
        _global_hook_registry = HookRegistry()
    return _global_hook_registry

def auto_hook(
    hook_type: HookType,
    priority: int = HookPriority.LOGGING,
    matcher: Optional[str] = None,
):
    """自动注册的 Hook 装饰器

    Args:
        hook_type: Hook 类型
        priority: 优先级
        matcher: 可选的匹配器（如工具名）
    """
    def decorator(func: Callable) -> Callable:
        # 1. 创建 Hook 并自动注册
        hook = Hook(
            name=func.__name__,
            hook_type=hook_type,
            handler=func,
            priority=priority,
        )
        get_hook_registry().register(hook)
        return func
    return decorator
```

### 5.2 使用方式

```python
# 装饰器自动注册
@auto_hook(HookType.TOOL_BEFORE, priority=HookPriority.LOGGING)
def log_tool_call(ctx: HookContext) -> None:
    """记录工具调用日志"""
    print(f"[Hook] Calling {ctx.data.get('tool_name')}")

@auto_hook(HookType.TOOL_BEFORE, priority=HookPriority.PERMISSION)
def check_permission(ctx: HookContext) -> None:
    """检查权限"""
    ...

# log_tool_call 和 check_permission 被装饰后，自动注册到 Registry
```

### 5.3 启动时扫描

```python
# 启动时扫描并注册所有内置 Hook

async def load_builtin_hooks():
    """加载所有内置 Hook（自动注册）"""
    import glob
    import importlib

    # 扫描 infra/hook/builtin/ 目录
    for file in glob.glob("infra/hook/builtin/*.py"):
        module_name = file.replace("/", ".").replace(".py", "")
        module = importlib.import_module(module_name)

        # 模块中所有 @auto_hook 装饰的函数已自动注册
        # 无需手动调用
```

---

## 6. Hook 注册表

```python
class HookRegistry:
    """Hook 注册表"""

    def __init__(self):
        self._hooks: dict[HookType, list[Hook]] = {}

    def register(self, hook: Hook) -> None:
        """注册 Hook"""
        if hook.hook_type not in self._hooks:
            self._hooks[hook.hook_type] = []
        self._hooks[hook.hook_type].append(hook)
        # 按优先级排序
        self._hooks[hook.hook_type].sort(key=lambda h: h.priority, reverse=True)

    def unregister(self, name: str) -> None:
        """注销 Hook"""
        for hooks in self._hooks.values():
            hooks[:] = [h for h in hooks if h.name != name]

    def emit(self, hook_type: HookType, context: HookContext) -> list[Any]:
        """触发 Hook"""
        results = []
        hooks = self._hooks.get(hook_type, [])
        for hook in hooks:
            try:
                result = hook._handler(context)
                results.append(result)
            except Exception as e:
                # Hook 执行出错不影响主流程
                logging.error(f"Hook {hook.name} failed: {e}")
        return results

    def get_hooks(self, hook_type: HookType) -> list[Hook]:
        """获取指定类型的 Hook"""
        return self._hooks.get(hook_type, [])
```

---

## 7. 使用示例

### 7.1 内置 Hook

```python
# 使用 @auto_hook 装饰器自动注册
@auto_hook(HookType.TOOL_BEFORE, priority=HookPriority.LOGGING)
def log_tool_call(ctx: HookContext) -> None:
    """记录工具调用日志"""
    print(f"[Hook] Calling {ctx.data.get('tool_name')}")

@auto_hook(HookType.TOOL_AFTER, priority=HookPriority.METRICS)
def record_metrics(ctx: HookContext) -> None:
    """记录工具指标"""
    metrics.increment(ctx.data.get("tool_name", "unknown"))

@auto_hook(HookType.TOOL_BEFORE, priority=HookPriority.PERMISSION)
def check_permission(ctx: HookContext) -> None:
    """检查权限（危险命令拦截）"""
    tool_name = ctx.data.get("tool_name", "")
    args = ctx.data.get("args", {})
    if is_dangerous_tool(tool_name, args):
        if not confirm_dangerous_operation(tool_name, args):
            raise PermissionDenied(f"Tool {tool_name} requires confirmation")
```

---

## 8. 与其他模块集成

### 8.1 与工具系统集成

ToolNode 是 LangGraph 内置的工具执行节点，我们需要创建一个包装器来触发 Hook：

```python
from langgraph.prebuilt import ToolNode
from langchain_core.messages import BaseMessage
from typing import Sequence


class HookableToolNode:
    """带 Hook 的 ToolNode 包装器"""

    def __init__(
        self,
        tools: list[BaseTool],
        hook_registry: HookRegistry = None,
    ):
        self._tool_node = ToolNode(tools)
        self._hook_registry = hook_registry or get_hook_registry()

    async def invoke(self, input_data: dict) -> dict:
        """执行工具并触发 Hook"""
        tool_calls = input_data.get("tool_calls", [])

        results = []
        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call.get("args", {})

            # 执行前 Hook
            self._hook_registry.emit(HookType.TOOL_BEFORE, HookContext(
                hook_type=HookType.TOOL_BEFORE,
                module="tool",
                event="execute",
                data={"tool_name": tool_name, "args": tool_args},
                timestamp=time.time(),
            ))

            try:
                result = await self._tool_node.invoke({"messages": [tool_call]})
                # 执行后 Hook
                self._hook_registry.emit(HookType.TOOL_AFTER, HookContext(
                    hook_type=HookType.TOOL_AFTER,
                    module="tool",
                    event="execute",
                    data={"tool_name": tool_name, "result": result},
                    timestamp=time.time(),
                ))
                results.append(result)
            except Exception as e:
                # 错误 Hook
                self._hook_registry.emit(HookType.TOOL_ERROR, HookContext(
                    hook_type=HookType.TOOL_ERROR,
                    module="tool",
                    event="execute",
                    data={"tool_name": tool_name, "error": str(e)},
                    timestamp=time.time(),
                ))
                raise

        return {"messages": results}
```

### 8.2 与 Agent 集成

```python
class Agent:
    def __init__(self, hook_registry: HookRegistry):
        self.hooks = hook_registry

    async def run(self, input_data: dict) -> dict:
        # Agent 开始
        self.hooks.emit(HookType.AGENT_START, HookContext(
            hook_type=HookType.AGENT_START,
            module="agent",
            event="run",
            data={"agent_id": self.id},
            timestamp=time.time(),
        ))

        try:
            result = await self._do_run(input_data)
            # Agent 结束
            self.hooks.emit(HookType.AGENT_END, HookContext(
                hook_type=HookType.AGENT_END,
                module="agent",
                event="run",
                data={"agent_id": self.id, "result": result},
                timestamp=time.time(),
            ))
            return result
        except Exception as e:
            # Agent 错误
            self.hooks.emit(HookType.AGENT_ERROR, HookContext(
                hook_type=HookType.AGENT_ERROR,
                module="agent",
                event="run",
                data={"agent_id": self.id, "error": str(e)},
                timestamp=time.time(),
            ))
            raise
```

---

## 9. 实现要点

1. **Hook 执行顺序**：按 priority 降序执行
2. **错误隔离**：Hook 执行失败不影响主流程
3. **线程安全**：多线程环境下 Hook 并发执行

---

## 10. 参考资料

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Python dataclasses](https://docs.python.org/3/library/dataclasses.html)