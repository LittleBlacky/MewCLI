# UI 交互架构 - 输出格式化

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. 格式化器

```python
class OutputFormatter:
    """输出格式化"""

    def __init__(self, config: FormatConfig):
        self.config = config

    def format_text(self, text: str) -> str:
        """格式化普通文本"""

    def format_code(self, code: str, language: str = "") -> str:
        """格式化代码"""

    def format_error(self, error: str) -> str:
        """格式化错误"""

    def format_table(self, data: list[dict]) -> str:
        """格式化表格"""

    def format_json(self, data: dict) -> str:
        """格式化 JSON"""

    def format_list(self, items: list[str]) -> str:
        """格式化列表"""
```

---

## 2. 代码高亮

```python
class CodeFormatter:
    """代码格式化"""

    SYNTAX_COLORS = {
        "keyword": "blue",
        "string": "green",
        "comment": "gray",
        "function": "yellow",
        "class": "cyan",
    }

    def highlight(self, code: str, language: str = "") -> str:
        """高亮代码"""
        # 使用 Pygments 或简单正则
        # ...

    def wrap_code_block(self, code: str, language: str = "") -> str:
        """包装代码块"""
        return f"```{language}\n{code}\n```"
```

---

## 3. 表格格式化

```python
def format_table(data: list[dict], headers: list[str] = None) -> str:
    """格式化表格"""
    if not data:
        return ""

    # 获取表头
    if headers is None:
        headers = list(data[0].keys())

    # 计算列宽
    col_widths = {}
    for header in headers:
        col_widths[header] = len(header)

    for row in data:
        for header in headers:
            col_widths[header] = max(col_widths[header], len(str(row.get(header, ""))))

    # 格式化表格
    lines = []

    # 表头
    header_line = " | ".join(header.ljust(col_widths[h]) for h in headers)
    lines.append(header_line)
    lines.append("-" * len(header_line))

    # 数据行
    for row in data:
        data_line = " | ".join(str(row.get(h, "")).ljust(col_widths[h]) for h in headers)
        lines.append(data_line)

    return "\n".join(lines)
```

---

## 4. 错误处理

### 4.1 错误格式化

```python
class ErrorFormatter:
    """错误格式化"""

    ERROR_COLORS = {
        "error": "red",
        "warning": "yellow",
        "info": "blue",
    }

    def format_error(self, error: Exception, verbose: bool = False) -> str:
        """格式化错误"""
        lines = []

        # 错误类型
        error_type = type(error).__name__
        lines.append(f"[Error] {error_type}")

        # 错误消息
        lines.append(f"  {error}")

        # 详细信息（verbose 模式）
        if verbose:
            lines.append("")
            lines.append("详细信息:")
            lines.append(f"  文件: {error.__traceback__.tb_frame.f_code.co_filename}")
            lines.append(f"  行号: {error.__traceback__.tb_lineno}")

        return "\n".join(lines)

    def format_tool_error(self, tool_name: str, error: str) -> str:
        """格式化工具错误"""
        return f"[Tool Error] {tool_name}\n  {error}"
```

### 4.2 错误恢复

```python
class ErrorRecovery:
    """错误恢复"""

    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries

    async def with_retry(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> Any:
        """带重试的执行"""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except RetryableError as e:
                last_error = e
                wait_time = 2 ** attempt  # 指数退避
                await asyncio.sleep(wait_time)

        raise last_error


class RetryableError(Exception):
    """可重试的错误"""
    pass
```

---

## 5. 相关文档

- [index.md](index.md) - UI 交互架构索引
- [repl.md](repl.md) - REPL 交互设计
- [cli.md](cli.md) - CLI 命令行界面
- [streaming.md](streaming.md) - 流式输出