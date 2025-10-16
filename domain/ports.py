from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Sequence, Optional

@dataclass
class ChatMessage:
    role: str
    content: str

class LLMClientPort(Protocol):
    def chat_completion(
        self,
        model: str,
        messages: Sequence[ChatMessage],
        temperature: float = 0.2,
    ) -> str: ...

class CodeReviewPort(Protocol):
    def review(
        self,
        language: str,
        code: str,
        extra_note: str = "",
        output_language: str = "vi",
        model: Optional[str] = None,
    ) -> str: ...

    def fix(
        self,
        language: str,
        code: str,
        review_summary: str = "",
        output_language: str = "vi",
        model: Optional[str] = None,
    ) -> str: ...