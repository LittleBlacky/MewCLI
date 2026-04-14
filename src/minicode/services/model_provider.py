"""Model provider services."""
import os
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Optional

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI


class ModelProvider(ABC):
    """Abstract model provider."""

    @abstractmethod
    async def ainvoke(self, messages: list, **kwargs) -> Any:
        """Async invoke."""
        pass

    @abstractmethod
    async def astream(self, messages: list, **kwargs) -> AsyncIterator[str]:
        """Async stream."""
        pass


class AnthropicProvider(ModelProvider):
    """Anthropic Claude provider."""

    def __init__(self, model: str = "claude-sonnet-4-7"):
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.client = ChatAnthropic(
            model=model,
            api_key=api_key,
        )

    async def ainvoke(self, messages: list, **kwargs) -> Any:
        return await self.client.ainvoke(messages, **kwargs)

    async def astream(self, messages: list, **kwargs) -> AsyncIterator[str]:
        async for chunk in self.client.astream(messages, **kwargs):
            if hasattr(chunk, "content"):
                yield chunk.content
            else:
                yield str(chunk)


class OpenAIProvider(ModelProvider):
    """OpenAI provider."""

    def __init__(self, model: str = "gpt-4o"):
        api_key = os.environ.get("OPENAI_API_KEY", "")
        self.client = ChatOpenAI(
            model=model,
            api_key=api_key,
        )

    async def ainvoke(self, messages: list, **kwargs) -> Any:
        return await self.client.ainvoke(messages, **kwargs)

    async def astream(self, messages: list, **kwargs) -> AsyncIterator[str]:
        async for chunk in self.client.astream(messages, **kwargs):
            if hasattr(chunk, "content"):
                yield chunk.content
            else:
                yield str(chunk)


def create_provider(provider: str = "anthropic", **kwargs) -> ModelProvider:
    """Factory to create model provider."""
    if provider == "anthropic":
        return AnthropicProvider(**kwargs)
    elif provider == "openai":
        return OpenAIProvider(**kwargs)
    else:
        raise ValueError(f"Unknown provider: {provider}")
