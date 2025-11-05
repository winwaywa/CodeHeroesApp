from typing import List
import tiktoken

from chat.chat_message import ChatMessage


def count_tokens_tiktoken(messages: List[ChatMessage], model: str) -> int:
    """
    Đếm token chính xác với tiktoken, dựa trên schema chat.
    Hỗ trợ tốt với các model ChatCompletion như gpt-3.5, gpt-4, gpt-4o...
    """
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")  # fallback an toàn

    tokens = 0
    for msg in messages:
        # Count tokens for role + content
        tokens += 4  # overhead mỗi message theo format OpenAI
        tokens += len(enc.encode(msg.role))
        tokens += len(enc.encode(msg.content or ""))

    tokens += 3  # overhead cho assistant trả lời
    return tokens