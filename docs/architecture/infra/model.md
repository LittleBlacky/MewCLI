# MiniCode 架构设计文档 - Model 模型抽象层

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. 设计目标

**Model 抽象层** - 统一管理多模型提供商，支持配置、调用、Prompt 缓存。

### 1.1 设计原则

| 原则 | 说明 | 原因 |
|------|------|------|
| **统一接口** | 屏蔽提供商差异 | 灵活切换 |
| **延迟初始化** | 按需创建客户端 | 性能优化 |
| **缓存支持** | 支持 Prompt 缓存 | 成本优化 |

### 1.2 为什么这样设计

| 设计决策 | 原因 | 好处 |
|----------|------|------|
| 抽象层封装 | 支持多模型提供商 | 灵活性 |
| 缓存预算管理 | Anthropic 有 200K 限制 | 避免超限 |
| 多厂商适配 | 各厂商 API 不同 | 统一使用 |

---

## 2. 模块结构

```
infra/model/
├── __init__.py          # 导出公共类型
├── client.py            # ModelClient 模型客户端
├── config.py            # ModelConfig 模型配置
├── factory.py           # create_chat_model 工厂函数
└── cache.py             # PromptCache 缓存管理
```

---

## 3. Model 配置

### 3.1 ModelConfig

```python
@dataclass
class ModelConfig:
    """模型配置"""
    provider: str = "anthropic"     # 模型提供商
    model: str = "claude-sonnet-4-7"  # 模型名称
    api_key: Optional[str] = None    # API Key
    base_url: Optional[str] = None   # Base URL（用于兼容）
    temperature: Optional[float] = None   # Temperature
    max_tokens: Optional[int] = None      # 最大 Token
    timeout: float = 60.0           # 超时时间
    max_retries: int = 3             # 最大重试次数
```

---

## 4. ModelClient 设计

### 4.1 核心接口

```python
class ModelClient:
    """模型客户端封装"""

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ):
        self._provider = provider
        self._model = model
        self._api_key = api_key
        self._base_url = base_url
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._kwargs = kwargs
        self._client: Optional[Any] = None

    @property
    def client(self) -> Any:
        """延迟初始化客户端"""
        if self._client is None:
            self._client = create_chat_model(
                self._provider,
                self._model,
                api_key=self._api_key,
                base_url=self._base_url,
                **self._kwargs,
            )
        return self._client

    def invoke(self, messages: list, **kwargs) -> Any:
        """同步调用"""
        return self.client.invoke(messages, **kwargs)

    def stream(self, messages: list, **kwargs) -> Any:
        """流式调用"""
        return self.client.stream(messages, **kwargs)

    def bind_tools(self, tools: list) -> Any:
        """绑定工具"""
        return self.client.bind_tools(tools)
```

### 4.2 工厂函数

```python
def create_chat_model(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    *,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    **kwargs,
) -> Any:
    """创建聊天模型"""
    from langchain.chat_models import init_chat_model
    from minicode.infra.config import get_config_manager

    config = get_config_manager()
    model_cfg = config.get_model_config()

    provider = provider or model_cfg.get("provider") or "anthropic"
    model = model or model_cfg.get("model") or "claude-sonnet-4-7"
    api_key = api_key or model_cfg.get("api_key")

    if not api_key:
        raise ValueError("API Key required: set MINICODE_API_KEY env or config")

    params = {"timeout": 60.0, "max_retries": 3}
    if api_key:
        params["api_key"] = api_key
    if base_url:
        params["base_url"] = base_url

    return init_chat_model(model, model_provider=provider, **params)
```

---

## 5. Prompt 缓存

Anthropic API 支持 Prompt Caching，可将静态内容（系统提示、知识库、技能）缓存以降低成本。

### 5.1 设计原则

| 原则 | 说明 | 原因 |
|------|------|------|
| **动静分离** | 静态内容缓存，动态内容不缓存 | 节省成本 |
| **自动插入** | 在构建 prompt 时自动添加缓存标记 | 简化使用 |
| **预算管理** | 管理缓存 Token 预算（最大 200K） | 避免超限 |

### 5.2 可缓存内容

| 内容 | 缓存 | 说明 |
|------|------|------|
| System Prompt | ✅ | 固定不变 |
| 项目知识 | ✅ | 相对稳定 |
| 技能定义 | ✅ | 很少变化 |
| 用户偏好 | ✅ | 长期有效 |
| 对话历史 | ❌ | 动态变化 |
| 当前输入 | ❌ | 每次不同 |

### 5.3 PromptCache 实现

```python
@dataclass
class PromptCache:
    """Prompt 缓存管理"""

    # 可缓存内容
    system_prompt: Optional[str] = None
    knowledge: Optional[str] = None
    skills: Optional[str] = None
    preferences: Optional[str] = None

    # 缓存预算
    max_cache_tokens: int = 200_000  # Anthropic 最大缓存限制

    # 缓存命中
    cache_hit: bool = False
    cache_tokens: int = 0

    def build_messages(
        self,
        user_input: str,
        conversation_history: list[dict] = None,
    ) -> list[dict]:
        """构建包含缓存标记的消息"""

        messages = []

        # 1. 构建缓存内容（如果存在）
        cache_content = []
        if self.system_prompt:
            cache_content.append({"type": "text", "text": self.system_prompt})
        if self.knowledge:
            cache_content.append({"type": "text", "text": self.knowledge})
        if self.skills:
            cache_content.append({"type": "text", "text": self.skills})

        # 2. 如果有缓存内容，添加缓存块
        if cache_content:
            cache_text = "\n\n".join(c["text"] for c in cache_content)
            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "cache_breakpoint",
                        "cache_control": {"type": "ephemeral"},
                    },
                    {"type": "text", "text": cache_text},
                ],
            })
            self.cache_hit = True
            self.cache_tokens = estimate_tokens(cache_text)

        # 3. 添加对话历史
        if conversation_history:
            for msg in conversation_history:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                })

        # 4. 添加当前输入
        messages.append({
            "role": "user",
            "content": user_input,
        })

        return messages
```

### 5.4 缓存预算管理

```python
class CacheBudgetManager:
    """缓存预算管理器"""

    def __init__(self, max_tokens: int = 200_000):
        self.max_tokens = max_tokens
        self.used_tokens: int = 0
        self.cache_hits: int = 0

    def add(self, tokens: int) -> bool:
        """尝试添加缓存内容"""
        if self.used_tokens + tokens > self.max_tokens:
            return False  # 超预算
        self.used_tokens += tokens
        self.cache_hits += 1
        return True

    def reset(self) -> None:
        """重置预算（每次请求）"""
        self.used_tokens = 0
```

### 5.5 多厂商支持

| 厂商 | 支持程度 | 机制 |
|------|----------|------|
| **Anthropic** | ✅ 完全支持 | `cache_breakpoint` + `cache_control: {type: "ephemeral"}` |
| **OpenAI** | ✅ 支持 | `cache_control` with `ephemeral` |
| **Google** | ⚠️ 部分支持 | 查看 Vertex AI 文档 |
| **其他** | ❌ 回退 | 缓存内容作为系统提示 |

### 5.6 ProviderCacheAdapter

```python
class ProviderCacheAdapter:
    """多厂商缓存适配器"""

    def __init__(self, provider: str):
        self.provider = provider

    def build_cached_messages(
        self,
        static_content: dict,
        user_input: str,
    ) -> list[dict]:
        """为不同厂商构建缓存消息"""
        if self.provider == "anthropic":
            return self._build_anthropic_cache(static_content, user_input)
        elif self.provider == "openai":
            return self._build_openai_cache(static_content, user_input)
        else:
            return self._build_fallback_messages(static_content, user_input)

    def _build_anthropic_cache(
        self,
        static_content: dict,
        user_input: str,
    ) -> list[dict]:
        """Anthropic 缓存格式"""
        # 实现 Anthropic 特定格式
        pass

    def _build_openai_cache(
        self,
        static_content: dict,
        user_input: str,
    ) -> list[dict]:
        """OpenAI 缓存格式"""
        # 实现 OpenAI 特定格式
        pass

    def _build_fallback_messages(
        self,
        static_content: dict,
        user_input: str,
    ) -> list[dict]:
        """回退格式：将缓存内容作为系统提示"""
        # 将静态内容合并到系统提示
        pass
```

### 5.7 使用示例

```python
# 异步调用带缓存
class CachedModelClient:
    """支持 Prompt 缓存的模型客户端"""

    def __init__(self, model: ModelClient):
        self.model = model
        self.prompt_cache = PromptCache()
        self.budget_manager = CacheBudgetManager()

    async def invoke(self, messages: list, **kwargs) -> Any:
        # 1. 提取静态内容并构建缓存
        # ...

        # 2. 如果在预算内，添加缓存块
        # ...

        # 3. 调用模型
        return await self.model.invoke(messages, **kwargs)
```

---

## 6. 实现要点

1. **延迟初始化**：客户端延迟初始化，避免启动开销
2. **缓存预算**：注意 Anthropic 200K 限制
3. **厂商适配**：不同厂商 API 格式不同

---

## 7. 参考资料

- [Anthropic Prompt Caching](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)
- [LangChain Chat Models](https://python.langchain.com/docs/integrations/chat/)
- [OpenAI Cache Control](https://platform.openai.com/docs/guides/prompt-caching)