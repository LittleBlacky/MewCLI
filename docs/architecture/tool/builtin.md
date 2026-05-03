# Tool 工具架构 - 内置工具集

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. 工具分类

| 类别           | 工具                                 | 说明       | 异步    |
| -------------- | ------------------------------------ | ---------- | ------- |
| **file**       | read_file, write_file, list_dir      | 文件操作   | ✅ 异步 |
| **bash**       | bash, shell                          | 命令执行   | ✅ 异步 |
| **search**     | grep, find, search_code              | 搜索       | ✅ 异步 |
| **task**       | create_task, update_task, list_tasks | 任务管理   | ✅ 异步 |
| **team**       | assign_task, get_worker_status       | 团队协作   | ✅ 异步 |
| **background** | run_background, list_background      | 后台任务   | ✅ 异步 |
| **memory**     | memory_save, memory_get, memory_list | 记忆管理   | ✅ 异步 |
| **permission** | check_permission, set_mode           | 权限控制   | ❌ 同步 |
| **mcp**        | mcp_tool_call                        | MCP 集成   | ✅ 异步 |
| **compact**    | compact_context                      | 上下文压缩 | ✅ 异步 |

> **注意**：permission 工具是同步的，因为它是内存操作，速度极快，不影响并发。

---

## 2. 文件操作工具

```python
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

## 3. Bash 工具（异步实现）

Bash 工具必须使用异步实现，否则会阻塞事件循环，导致多 Worker 无法真正并行。

```python
@auto_tool
async def bash(command: str, timeout: int = 60, cwd: Optional[str] = None) -> str:
    """执行 Bash 命令（异步实现，不阻塞事件循环）

    Args:
        command: Bash 命令
        timeout: 超时时间（秒）
        cwd: 工作目录
    """
    import asyncio

    # 使用 asyncio.create_subprocess_shell 实现真正的异步
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )

    # 带超时等待
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        proc.kill()
        return f"[Timeout] Command exceeded {timeout}s"

    # 返回结果
    output = (stdout + stderr).decode('utf-8', errors='replace').strip()
    return output[:50000] if output else "(no output)"
```

---

## 4. 其他 I/O 工具的异步模式

所有 I/O 密集型工具都应遵循以下模式：

| 工具类型     | 实现方式                          | 示例                  |
| ------------ | --------------------------------- | --------------------- |
| **子进程**   | `asyncio.create_subprocess_*`     | bash, shell           |
| **文件 I/O** | `aiofiles` 或 `asyncio.to_thread` | read_file, write_file |
| **网络请求** | `aiohttp` 或 `httpx.AsyncClient`  | HTTP 调用             |
| **数据库**   | 异步驱动 (asyncpg, aiomysql)      | 数据库操作            |
| **快速工具** | 可用同步（不阻塞）                | 数学计算、字符串处理  |

---

## 5. 搜索工具

```python
@auto_tool
def grep(pattern: str, path: str = ".", recursive: bool = False) -> str:
    """搜索文件内容

    Args:
        pattern: 搜索模式
        path: 搜索路径
        recursive: 是否递归搜索
    """
    import subprocess
    cmd = ["grep", "-r", pattern, path] if recursive else ["grep", pattern, path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout or "(no matches)"

@auto_tool
def find(name: str, path: str = ".") -> str:
    """查找文件

    Args:
        name: 文件名模式
        path: 搜索路径
    """
    import subprocess
    result = subprocess.run(
        ["find", path, "-name", name],
        capture_output=True,
        text=True,
    )
    return result.stdout or "(no matches)"
```

---

## 6. 相关文档

- [index.md](index.md) - 工具架构索引
- [registry.md](registry.md) - 工具注册表
- [permission.md](permission.md) - 权限控制系统
