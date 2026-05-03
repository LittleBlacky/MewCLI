# Tool 工具架构 - 工具注册表

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. 为什么需要注册表

ToolNode 可以直接执行工具，但缺少：

- **权限控制**：危险命令（rm -rf、sudo）需要确认
- **MCP 动态注册**：MCP 服务器可随时加载/卸载
- **工具列表查询**：需要知道有哪些可用工具

---

## 2. ToolRegistry 实现

```python
# registry.py - 工具注册表 = 工具管理 + MCP 动态加载

from langchain_core.tools import BaseTool
from typing import Optional

class ToolRegistry:
    """工具注册表 - 管理 @tool 装饰的函数，支持 MCP 动态注册"""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """注册工具"""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        """获取工具"""
        return self._tools.get(name)

    def list_all(self) -> list[BaseTool]:
        """列出所有工具"""
        return list(self._tools.values())

    def unregister(self, name: str) -> bool:
        """注销工具（MCP 卸载时用到）"""
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    def to_langgraph_tools(self) -> list[BaseTool]:
        """导出给 ToolNode 使用"""
        return list(self._tools.values())
```

---

## 3. 自动注册机制

**问题**：手动 `registry.register()` 太繁琐

**解决方案**：装饰器自动注册

```python
# registry.py - 自动注册机制

from langchain_core.tools import tool, BaseTool
from typing import Optional

# 全局注册表（单例）
_global_registry: Optional["ToolRegistry"] = None

def get_registry() -> "ToolRegistry":
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry

def auto_tool(func):
    """自动注册的 @tool 装饰器"""
    # 1. 调用原始 @tool 装饰器
    langchain_tool = tool(func)

    # 2. 自动注册到全局 Registry
    get_registry().register(langchain_tool)

    return langchain_tool

# 使用方式：和普通 @tool 一样，但会自动注册
@auto_tool
def read_file(file_path: str, ...) -> str:
    """读取文件内容"""
    ...

# read_file 被装饰后，自动注册到 Registry
```

---

## 4. 启动时扫描

```python
# 启动时扫描并注册所有内置工具

async def load_builtin_tools():
    """加载所有内置工具（自动注册）"""
    import glob
    import importlib

    # 扫描 tool/builtin/ 目录
    for file in glob.glob("tool/builtin/*.py"):
        module_name = file.replace("/", ".").replace(".py", "")
        module = importlib.import_module(module_name)

        # 模块中所有 @auto_tool 装饰的函数已自动注册
        # 无需手动调用

    # 注册给 ToolNode
    registry = get_registry()
    return ToolNode(registry.to_langgraph_tools())
```

---

## 5. 工具定义

**工具 = `@auto_tool` 装饰的函数（定义 + 执行 + 自动注册）**：

```python
from langchain_core.tools import tool
from typing import Optional

@auto_tool
def read_file(file_path: str, limit: Optional[int] = None, offset: int = 0) -> str:
    """读取文件内容

    Args:
        file_path: 文件路径
        limit: 限制行数
        offset: 起始行偏移
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        if offset:
            f.seek(offset)
        return f.read() if not limit else ''.join(f.readline() for _ in range(limit))

@auto_tool
def write_file(file_path: str, content: str, append: bool = False) -> str:
    """写入文件内容

    Args:
        file_path: 文件路径
        content: 文件内容
        append: 是否追加模式
    """
    mode = 'a' if append else 'w'
    with open(file_path, mode, encoding='utf-8') as f:
        f.write(content)
    return f"Written to {file_path}"

@auto_tool
def list_dir(path: str = ".") -> str:
    """列出目录内容"""
    import os
    return '\n'.join(os.listdir(path))
```

---

## 6. 注册流程

```python
# 完全自动化，无需手动 register()

# 1. 定义工具时用 @auto_tool（自动注册）
@auto_tool
def bash(command: str, ...) -> str: ...

# 2. 启动时扫描内置工具
await load_builtin_tools()  # 扫描 tool/builtin/*.py

# 3. 注册 MCP 工具（需要手动注册，因为来自外部）
await mcp_manager.load_server(config)
for mcp_tool in mcp_manager.list_tools():
    get_registry().register(mcp_tool)

# 4. 导出给 ToolNode
tool_node = ToolNode(get_registry().to_langgraph_tools())
```

---

## 7. 与其他模块集成

### 7.1 与 Agent 集成

```python
# infra/graph.py

from langgraph.prebuilt import ToolNode

def build_graph():
    """构建 Agent Graph"""
    tools = get_registry().to_langgraph_tools()
    tool_node = ToolNode(tools)

    builder = StateGraph(AgentState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)

    builder.add_edge("agent", "tools")
    builder.add_conditional_edges("agent", should_continue, ...)

    return builder.compile()
```

### 7.2 Lead/Worker 工具共享

**工具访问权限**：Lead Agent 和 Worker Agent 共享全部工具

| Agent 类型   | 工具访问 | 说明                         |
| ------------ | -------- | ---------------------------- |
| Lead Agent   | 全部工具 | 完整工具集，包括工具注册权限 |
| Worker Agent | 全部工具 | 与 Lead 相同的工具集         |

---

## 8. 相关文档

- [index.md](index.md) - 工具架构索引
- [builtin.md](builtin.md) - 内置工具集
- [permission.md](permission.md) - 权限控制系统
