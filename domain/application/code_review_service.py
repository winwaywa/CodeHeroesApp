import logging
from typing import Optional
from domain.ports import LLMClientPort, CodeReviewPort, ChatMessage
from domain.application.prompts import (
    review_system_prompt,
    build_review_user_prompt,
    fix_system_prompt,
    build_fix_user_prompt,
)
from config.logger import logger

class CodeReviewService(CodeReviewPort):
    def __init__(self, client: LLMClientPort, default_model: Optional[str] = None):
        self.client = client
        self.default_model = default_model

    def review(self, language: str, code: str, extra_note: str = "", output_language: str = "vietnamese", model: Optional[str] = None) -> str:
        sys = review_system_prompt(language)
        user = build_review_user_prompt(language, code, extra_note, output_language)
        logger.info("[Review] System prompt: " + sys)
        logger.info("[Review] User prompt: " + user)
        return self.client.chat_completion(
            model=model or self.default_model or "gpt-4o-mini",
            messages=[
                ChatMessage("system", sys),
                ChatMessage("user", user),
            ],
            temperature=0.2,
        )

    def fix(self, language: str, code: str, review_summary: str = "", output_language: str = "vietnamese", model: Optional[str] = None) -> str:
        sys = fix_system_prompt(language)
        user = build_fix_user_prompt(language, code, review_summary, output_language)
        logger.info("[Fix] System prompt: " + sys)
        logger.info("[Fix] User prompt: " + user)
        return self.client.chat_completion(
            model=model or self.default_model or "gpt-4o-mini",
            messages=[
                ChatMessage("system", sys),
                ChatMessage("user", user),
            ],
            temperature=0.1,
        )