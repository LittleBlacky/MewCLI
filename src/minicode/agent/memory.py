"""Memory Layer - 记忆检索、注入和整合"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Optional, TypedDict
from dataclasses import dataclass

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage


WORKDIR = Path.cwd()
MEMORY_DIR = WORKDIR / ".mini-agent-cli" / ".memory"


@dataclass
class MemoryEntry:
    """记忆条目"""
    name: str
    description: str
    content: str
    memory_type: str  # user, feedback, project, reference
    created_at: float
    access_count: int = 0
    last_accessed: float = 0


class MemoryIndex:
    """记忆索引 - 快速检索"""

    def __init__(self, memory_dir: Path = MEMORY_DIR):
        self.memory_dir = memory_dir
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._index: dict[str, MemoryEntry] = {}
        self._load_index()

    def _load_index(self) -> None:
        """加载索引"""
        self._index.clear()
        for md_file in self.memory_dir.glob("*.md"):
            if md_file.name == "MEMORY.md":
                continue
            entry = self._parse_memory_file(md_file)
            if entry:
                self._index[entry.name] = entry

    def _parse_memory_file(self, file_path: Path) -> Optional[MemoryEntry]:
        """解析记忆文件"""
        try:
            text = file_path.read_text(encoding="utf-8")
            match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
            if not match:
                return None

            header, content = match.groups()
            meta = {}
            for line in header.splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    meta[k.strip()] = v.strip()

            created_match = re.search(r"created_at:\s*(.+)", header)
            created_at = float(created_match.group(1)) if created_match else time.time()

            return MemoryEntry(
                name=meta.get("name", file_path.stem),
                description=meta.get("description", ""),
                content=content.strip(),
                memory_type=meta.get("type", "unknown"),
                created_at=created_at,
            )
        except Exception:
            return None

    def save_entry(self, entry: MemoryEntry) -> None:
        """保存记忆条目"""
        safe_name = entry.name.replace(" ", "-").lower()
        file_path = self.memory_dir / f"{safe_name}.md"

        frontmatter = f"""---
name: {entry.name}
description: {entry.description}
type: {entry.memory_type}
created_at: {entry.created_at}
access_count: {entry.access_count}
---

{entry.content}
"""
        file_path.write_text(frontmatter, encoding="utf-8")
        self._index[entry.name] = entry

    def search(self, query: str, memory_type: Optional[str] = None, limit: int = 3) -> list[MemoryEntry]:
        """搜索相关记忆"""
        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored = []
        for name, entry in self._index.items():
            # 类型过滤
            if memory_type and entry.memory_type != memory_type:
                continue

            # 计算相关性分数
            score = 0

            # 标题匹配
            if query_lower in entry.name.lower():
                score += 10

            # 描述匹配
            if query_lower in entry.description.lower():
                score += 5

            # 内容匹配
            for word in query_words:
                if word in entry.content.lower():
                    score += 1

            # 访问频率加成
            score += min(entry.access_count * 0.1, 2)

            if score > 0:
                scored.append((score, entry))

        # 排序并返回
        scored.sort(key=lambda x: x[0], reverse=True)
        results = [entry for _, entry in scored[:limit]]

        # 更新访问记录
        for entry in results:
            entry.access_count += 1
            entry.last_accessed = time.time()
            self.save_entry(entry)

        return results

    def list_all(self) -> list[dict]:
        """列出所有记忆"""
        return [
            {
                "name": e.name,
                "description": e.description,
                "type": e.memory_type,
                "created_at": e.created_at,
            }
            for e in self._index.values()
        ]

    def consolidate(self, max_memories: int = 20) -> list[str]:
        """整合记忆 - 合并相似记忆"""
        # 按类型分组
        by_type: dict[str, list[MemoryEntry]] = {}
        for entry in self._index.values():
            if entry.memory_type not in by_type:
                by_type[entry.memory_type] = []
            by_type[entry.memory_type].append(entry)

        # 保留最新和最常用的
        deleted = []
        for mem_type, entries in by_type.items():
            if len(entries) > max_memories:
                # 按访问次数和创建时间排序
                entries.sort(key=lambda e: (e.access_count, e.created_at), reverse=True)

                # 删除最旧的
                for entry in entries[max_memories:]:
                    safe_name = entry.name.replace(" ", "-").lower()
                    file_path = self.memory_dir / f"{safe_name}.md"
                    if file_path.exists():
                        file_path.unlink()
                        deleted.append(entry.name)
                        del self._index[entry.name]

        self._load_index()
        return deleted


class MemoryLayer:
    """记忆层 - 检索、注入、整合"""

    def __init__(self):
        self.index = MemoryIndex()
        self.relevance_threshold = 2.0  # 相关性阈值
        self.max_inject_memories = 3    # 最多注入3条记忆

    def retrieve(self, query: str, memory_type: Optional[str] = None) -> list[MemoryEntry]:
        """检索相关记忆"""
        return self.index.search(query, memory_type, limit=self.max_inject_memories)

    def inject_memories(self, query: str) -> str:
        """生成记忆注入文本"""
        memories = self.retrieve(query)

        if not memories:
            return ""

        injected = ["\n\n## 相关记忆\n"]
        for m in memories:
            injected.append(f"### [{m.memory_type}] {m.name}")
            injected.append(m.content[:500])  # 最多500字符
            injected.append("")

        return "\n".join(injected)

    def save(
        self,
        name: str,
        content: str,
        memory_type: str,
        description: str = "",
    ) -> str:
        """保存记忆"""
        entry = MemoryEntry(
            name=name,
            description=description,
            content=content,
            memory_type=memory_type,
            created_at=time.time(),
        )
        self.index.save_entry(entry)
        return f"Saved memory: {name}"

    def consolidate(self) -> dict:
        """运行记忆整合"""
        deleted = self.index.consolidate(max_memories=20)
        return {
            "action": "consolidate",
            "deleted": deleted,
            "remaining": len(self.index._index),
        }

    def list_all(self) -> list[dict]:
        """列出所有记忆"""
        return self.index.list_all()

    def get_stats(self) -> dict:
        """获取记忆统计"""
        by_type: dict[str, int] = {}
        for entry in self.index._index.values():
            by_type[entry.memory_type] = by_type.get(entry.memory_type, 0) + 1

        return {
            "total": len(self.index._index),
            "by_type": by_type,
        }


# 全局实例
_memory_layer: Optional[MemoryLayer] = None


def get_memory_layer() -> MemoryLayer:
    """获取全局记忆层"""
    global _memory_layer
    if _memory_layer is None:
        _memory_layer = MemoryLayer()
    return _memory_layer
