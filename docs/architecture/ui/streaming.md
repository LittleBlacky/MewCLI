# UI 交互架构 - 流式输出

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. 流式响应

```python
class StreamingOutput:
    """流式输出"""

    def __init__(self, output: TextIO = sys.stdout):
        self.output = output

    async def stream_response(self, response: str) -> None:
        """流式输出响应"""
        for chunk in self._split_chunks(response):
            self.output.write(chunk)
            self.output.flush()

        self.output.write("\n")

    def _split_chunks(self, text: str) -> generator:
        """拆分文本为块"""
        # 按单词或句子拆分
        words = text.split()
        for word in words:
            yield word + " "
            if len(word) > 20:
                yield " "
```

---

## 2. 流式合并

```python
class StreamingAggregator:
    """流式聚合器"""

    def __init__(self):
        self._buffer = ""
        self._tool_calls = []
        self._final_result = ""

    async def on_chunk(self, chunk: str) -> None:
        """处理流式块"""
        self._buffer += chunk

        # 检测工具调用
        if self._is_tool_call_start(self._buffer):
            self._tool_calls.append(chunk)
        elif self._is_tool_call_end(self._buffer):
            self._tool_calls.append(chunk)
            # 处理工具调用
            await self._process_tool_calls()
        else:
            # 普通文本
            yield chunk

    def _is_tool_call_start(self, buffer: str) -> bool:
        """检测工具调用开始"""
        return "tool_calls" in buffer or "<tool_call>" in buffer

    def _is_tool_call_end(self, buffer: str) -> bool:
        """检测工具调用结束"""
        return "</tool_call>" in buffer or '"]}' in buffer
```

---

## 3. 快捷键支持

### 3.1 快捷键映射

```python
KEYBOARD_SHORTCUTS = {
    # 导航
    "ctrl+c": "interrupt",      # 中断输入
    "ctrl+d": "eof",            # 结束输入
    "ctrl+l": "clear",          # 清屏
    "ctrl+u": "clear_line",     # 清空当前行

    # 历史
    "up": "history_up",         # 上一个命令
    "down": "history_down",     # 下一个命令
    "ctrl+r": "search_history",  # 搜索历史

    # 编辑
    "ctrl+a": "beginning_of_line",   # 行首
    "ctrl+e": "end_of_line",         # 行尾
    "ctrl+k": "kill_line",           # 删除到行尾
    "ctrl+w": "kill_word",           # 删除单词

    # 命令
    "tab": "complete",          # 自动补全
    "ctrl+c": "cancel",         # 取消当前命令
}
```

### 3.2 自动补全

```python
class Completer:
    """自动补全器"""

    def __init__(self):
        self._commands = list(COMMANDS.keys())
        self._tools = self._load_tools()

    def complete(self, text: str) -> list[str]:
        """补全文本"""
        # 补全命令
        if text.startswith("/"):
            return [c for c in self._commands if c.startswith(text)]

        # 补全工具
        if text.startswith("tool:"):
            tool_name = text.replace("tool:", "")
            return [f"tool:{t}" for t in self._tools if t.startswith(tool_name)]

        # 补全文件路径
        if text.startswith("."):
            return self._complete_path(text)

        return []

    def _complete_path(self, path: str) -> list[str]:
        """补全文件路径"""
        # ...
```

---

## 4. 相关文档

- [index.md](index.md) - UI 交互架构索引
- [repl.md](repl.md) - REPL 交互设计
- [cli.md](cli.md) - CLI 命令行界面
- [formatter.md](formatter.md) - 输出格式化