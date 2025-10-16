from typing import Sequence
from openai import AzureOpenAI
from domain.ports import LLMClientPort, ChatMessage
from infra.providers.base import ProviderConfig, ProviderConfigError

class AzureOpenAIClient(LLMClientPort):
    def __init__(self, cfg: ProviderConfig):
        self._client = AzureOpenAI(
            api_key=cfg.api_key,
            azure_endpoint=cfg.azure_api_base,
            api_version=cfg.azure_api_version,
        )

    def chat_completion(self, model: str, messages: Sequence[ChatMessage], temperature: float = 0.2) -> str:
        resp = self._client.chat.completions.create(
            model=model,  # deployment name
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""