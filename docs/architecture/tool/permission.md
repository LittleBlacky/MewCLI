# Tool 工具架构 - 权限控制系统

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. 权限架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Permission System                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   Allow    │    │   Deny     │    │   Prompt   │     │
│  │   List     │    │   List     │    │   Rules    │     │
│  └──────┬─────┘    └──────┬─────┘    └──────┬─────┘     │
│         │                   │                   │            │
│         └───────────────────┼───────────────────┘          │
│                             │                               │
│                             ▼                               │
│                   ┌─────────────────┐                       │
│                   │ PermissionCheck │                      │
│                   │     权限检查     │                       │
│                   └────────┬────────┘                       │
│                            │                                │
│         ┌──────────────────┼──────────────────┐            │
│         │                  │                  │             │
│         ▼                  ▼                  ▼             │
│  ┌───────────┐    ┌───────────┐    ┌───────────┐          │
│  │   Safe    │    │  Dangerous │    │  Unknown  │          │
│  │    安全    │    │    危险    │    │   未知    │          │
│  └─────┬─────┘    └─────┬─────┘    └─────┬─────┘          │
│        │                 │                 │                │
│        ▼                 ▼                 ▼                │
│   直接执行          需要确认         用户选择                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 内置危险模式

```python
BUILTIN_DANGEROUS_PATTERNS = [
    # 高风险
    ("rm_rf", r"rm\s+-rf", "high", "递归删除，可能导致数据丢失"),
    ("sudo", r"sudo\s+", "high", "使用 sudo 权限"),
    ("dd", r"\bdd\b", "critical", "磁盘操作，风险极高"),
    ("mkfs", r"mkfs", "critical", "格式化，风险极高"),

    # 中风险
    ("chmod", r"chmod\s+777", "medium", "777 权限过于开放"),
    ("kill", r"kill\s+-\s*9", "medium", "强制终止进程"),
    ("curl_pipe", r"curl.+\|", "medium", "远程脚本执行"),

    # 低风险
    ("restart", r"(systemctl|service)\s+restart", "low", "服务重启"),
    ("git_force", r"git\s+push\s+--force", "low", "强制推送"),
]
```

---

## 3. 权限检查流程

```python
class PermissionConfig:
    """权限配置"""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path.home() / ".minicode" / "permissions.yaml"
        self._load_config()

    def check(self, command: str) -> tuple[bool, str, str, str]:
        """检查命令权限

        Returns: (allowed, reason, risk, suggested_pattern)
        """
        # 1. 检查允许列表
        for pattern in self.allow_patterns:
            if re.search(pattern, command):
                return True, "Allowed by user config", "low", pattern

        # 2. 检查拒绝列表
        for pattern in self.deny_patterns:
            if re.search(pattern, command):
                return False, "Denied by user config", "high", pattern

        # 3. 检查内置危险模式
        for name, pattern, risk, desc in BUILTIN_DANGEROUS_PATTERNS:
            if re.search(pattern, command):
                return False, f"Dangerous: {desc}", risk, name

        # 4. 未知命令
        if self.prompt_unknown:
            return True, "Requires confirmation", "medium", self._extract_pattern(command)

        return True, "", "low", ""

    def needs_prompt(self, command: str) -> bool:
        """是否需要用户确认"""
        allowed, reason, risk, _ = self.check(command)
        if not allowed:
            return True
        if risk in ("high", "critical"):
            return True
        return False
```

---

## 4. 权限确认选项

```python
def ask_permission(command: str) -> str:
    """生成权限确认提示"""
    message = f"""
命令: {command}
风险: {get_risk_level(command)}

选项:
  [y] 仅允许这一次
  [a] 允许当前命令类型的所有变体
  [n] 仅拒绝这一次
  [d] 永久加入 deny 列表

请输入选择 (y/a/n/d):"""
    return message
```

---

## 5. 权限控制（Hook）

权限检查通过 Hook（priority=100）实现：

```python
# infra/hook/permission.py

async def check_permission(state: GraphState, config: RunnableConfig):
    """执行前检查权限（Hook priority=100）"""
    messages = state.get("messages", [])
    last_msg = messages[-1] if messages else None

    # 获取当前工具调用
    if hasattr(last_msg, "tool_calls"):
        for tool_call in last_msg.tool_calls:
            tool_name = tool_call["name"]
            args = tool_call["args"]

            # 危险命令检查
            if is_dangerous_tool(tool_name, args):
                if not await confirm_dangerous_operation(tool_name, args):
                    raise PermissionDenied(f"Tool {tool_name} requires confirmation")
```

---

## 6. 执行流程

```
                    Agent 请求执行工具
                         │
                         ▼
              ┌─────────────────────────┐
              │      ToolNode           │
              │   接收 tool_calls       │
              └───────────┬─────────────┘
                          │
              ┌───────────┴───────────┐
              │                       │
              ▼                       ▼
        正常工具                  危险工具
              │                       │
              │                       ▼
              │            ┌─────────────────────────┐
              │            │   Hook 检查权限        │
              │            │   (priority=100)       │
              │            └───────────┬─────────────┘
              │                        │
              │            ┌───────────┴───────────┐
              │            │                       │
              ▼            ▼                       ▼
         ToolNode       确认后执行              拒绝
         直接执行        继续 ToolNode          抛出异常
```

---

## 7. 工具钩子

```python
class ToolHooks:
    """工具钩子"""

    def __init__(self):
        self._before_hooks: list[Callable] = []
        self._after_hooks: list[Callable] = []
        self._error_hooks: list[Callable] = []

    def before_execute(self, hook: Callable) -> None:
        """执行前钩子"""

    def after_execute(self, hook: Callable) -> None:
        """执行后钩子"""

    def on_error(self, hook: Callable) -> None:
        """错误钩子"""
```

### 7.1 钩子示例

```python
# 日志钩子
def log_tool_call(tool_name: str, args: dict):
    logger.info(f"Tool call: {tool_name}({args})")

# 指标钩子
def record_metrics(tool_name: str, result: ToolResult):
    metrics.increment("tool_calls", tags={"tool": tool_name})
    if not result.success:
        metrics.increment("tool_errors", tags={"tool": tool_name})

# 权限钩子
def check_dangerous_tool(tool_name: str, args: dict):
    if tool_name == "bash" and args.get("dangerous"):
        raise PermissionError("Dangerous tool call blocked")

hooks.before_execute(log_tool_call)
hooks.after_execute(record_metrics)
hooks.before_execute(check_dangerous_tool)
```

---

## 8. 工具指标

```python
@dataclass
class ToolMetrics:
    """工具指标"""
    tool_calls: dict = field(default_factory=dict)      # 调用次数
    tool_success_rate: dict = field(default_factory=dict)  # 成功率
    avg_tool_call_duration_ms: float = 0.0            # 平均耗时

    def record(
        self,
        tool_name: str,
        duration: float,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """记录工具调用"""
        # 更新调用次数
        self.tool_calls[tool_name] = self.tool_calls.get(tool_name, 0) + 1

        # 更新成功率
        if tool_name not in self.tool_success_rate:
            self.tool_success_rate[tool_name] = {"success": 0, "total": 0}

        stats = self.tool_success_rate[tool_name]
        stats["total"] += 1
        if success:
            stats["success"] += 1

    def get_success_rate(self, tool_name: str) -> float:
        """获取成功率"""
        stats = self.tool_success_rate.get(tool_name)
        if not stats or stats["total"] == 0:
            return 0.0
        return stats["success"] / stats["total"]
```

---

## 9. 相关文档

- [index.md](index.md) - 工具架构索引
- [registry.md](registry.md) - 工具注册表
- [builtin.md](builtin.md) - 内置工具集
