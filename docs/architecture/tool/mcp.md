# Tool 工具架构 - MCP 集成

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. MCP 架构

```
┌─────────────────────────────────────────────────────────────┐
│                      MCP System                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   MCP       │    │   MCP       │    │   MCP       │     │
│  │  Server 1   │    │  Server 2   │    │  Server N   │     │
│  │ (文件系统)   │    │ (数据库)    │    │   (自定义)  │     │
│  └──────┬─────┘    └──────┬─────┘    └──────┬─────┘     │
│         │                   │                   │            │
│         └───────────────────┼───────────────────┘          │
│                             │                               │
│                             ▼                               │
│                   ┌─────────────────┐                       │
│                   │   MCP Client    │                       │
│                   │   (MCP 客户端)   │                       │
│                   └────────┬────────┘                       │
│                            │                                │
│                            ▼                                │
│                   ┌─────────────────┐                       │
│                   │  Tool Adapter   │                       │
│                   │   (工具适配器)   │                       │
│                   └────────┬────────┘                       │
│                            │                                │
│                            ▼                                │
│                   ┌─────────────────┐                       │
│                   │  Tool Registry  │                       │
│                   │   (工具注册表)   │                       │
│                   └─────────────────┘                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. MCP 工具适配

```python
class MCPToolAdapter:
    """MCP 工具适配器"""

    def __init__(self, mcp_server: MCPServer):
        self.server = mcp_server

    def to_langchain_tool(self, mcp_tool: MCPTool) -> Tool:
        """将 MCP 工具转换为 LangChain 工具"""
        return Tool(
            name=mcp_tool.name,
            description=mcp_tool.description,
            parameters=mcp_tool.inputSchema,
            func=self._create_wrapper(mcp_tool),
        )

    async def call_tool(self, tool_name: str, arguments: dict) -> Any:
        """调用 MCP 工具"""
        return await self.server.call_tool(tool_name, arguments)
```

---

## 3. MCP 工具注册

```python
class MCPToolManager:
    """MCP 工具管理器"""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self._servers: dict[str, MCPServer] = {}

    async def load_server(self, config: MCPConfig) -> None:
        """加载 MCP 服务器"""
        server = MCPServer(config)
        await server.connect()

        # 注册所有工具
        for mcp_tool in await server.list_tools():
            tool = MCPToolAdapter(server).to_langchain_tool(mcp_tool)
            self.registry.register(tool, category="mcp")

        self._servers[config.name] = server

    async def unload_server(self, name: str) -> None:
        """卸载 MCP 服务器"""
        if name in self._servers:
            await self._servers[name].disconnect()
            del self._servers[name]
```

---

## 4. 初始化流程

```python
# main.py

async def init_tools():
    """初始化工具系统"""
    # 1. 扫描内置工具（@auto_tool 已自动注册）
    await load_builtin_tools()

    # 2. 加载 MCP 工具
    await mcp_manager.load_server(config)
    for mcp_tool in mcp_manager.list_tools():
        get_registry().register(mcp_tool)

    # 3. 创建 ToolNode
    registry = get_registry()
    tool_node = ToolNode(registry.to_langgraph_tools())

    # 4. 注册权限 Hook
    hook_manager.register("before_tool", check_permission, priority=100)

    return tool_node
```

---

## 5. 相关文档

- [index.md](index.md) - 工具架构索引
- [registry.md](registry.md) - 工具注册表
- [builtin.md](builtin.md) - 内置工具集
- [permission.md](permission.md) - 权限控制系统
