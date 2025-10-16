from typing import Sequence
from openai import OpenAI
from domain.ports import LLMClientPort, ChatMessage
from infra.providers.base import ProviderConfig, ProviderConfigError

class OpenAIClient(LLMClientPort):
    def __init__(self, cfg: ProviderConfig):
        self._client = OpenAI(api_key=cfg.api_key)

    def chat_completion(self, model: str, messages: Sequence[ChatMessage], temperature: float = 0.2) -> str:
        resp = self._client.chat.completions.create(
            model=model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""