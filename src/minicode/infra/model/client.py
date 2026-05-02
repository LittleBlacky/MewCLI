"""Model client - model provider abstraction."""
from __future__ import annotations

from typing import Any, Optional

from .config import ModelConfig


def create_chat_model(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    *,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    **kwargs,
) -> Any:
    """Create chat model using langchain init_chat_model."""
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


class ModelClient:
    """Model client wrapper with lazy initialization."""

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
        if self._client is None:
            self._client = create_chat_model(
                self._provider,
                self._model,
                api_key=self._api_key,
                base_url=self._base_url,
                **self._kwargs,
            )
        return self._client

    def invoke(self, messages: list, **kwargs):
        return self.client.invoke(messages, **kwargs)

    def stream(self, messages: list, **kwargs):
        return self.client.stream(messages, **kwargs)

    def bind_tools(self, tools: list) -> Any:
        return self.client.bind_tools(tools)

    def get_config(self) -> ModelConfig:
        from minicode.infra.config import get_config_manager

        config = get_config_manager()
        model_cfg = config.get_model_config()
        return ModelConfig(
            provider=self._provider or model_cfg.get("provider", "anthropic"),
            model=self._model or model_cfg.get("model", "claude-sonnet-4-7"),
            api_key=self._api_key or model_cfg.get("api_key"),
            base_url=self._base_url or model_cfg.get("base_url"),
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )

    def reset(self) -> None:
        self._client = None