# infra/llm/openai_client.py
from typing import List, Optional, Dict, Any
from chat.chat_message import ChatMessage
from chat.llm.chat_client import ChatClient

class OpenAIChatClient(ChatClient):
    """
    Dành cho OpenAI chuẩn (api.openai.com).
    Yêu cầu: pip install openai>=1.40
    """
    def __init__(self, *, api_key: str):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)

    def chat_completion(
        self,
        *,
        model: str,
        messages: List[ChatMessage],
        temperature: float = 0.3,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        return_raw: bool = False,
    ) -> Any:
        msgs = [{"role": m.role, "content": m.content} for m in messages]
        kwargs: Dict[str, Any] = {"model": model, "messages": msgs, "temperature": temperature}
        if tools is not None:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice  # "auto" | {"type":"function","function":{"name":...}}

        resp = self.client.chat.completions.create(**kwargs)

        if return_raw:
            # Chuẩn hoá về dict đơn giản để service xử lý tool_calls
            return {
                "choices": [
                    {
                        "message": {
                            "role": getattr(resp.choices[0].message, "role", "assistant"),
                            "content": resp.choices[0].message.content,
                            "tool_calls": [
                                {
                                    "id": tc.id,
                                    "type": tc.type,
                                    "function": {
                                        "name": tc.function.name,
                                        "arguments": tc.function.arguments,
                                    },
                                }
                                for tc in (resp.choices[0].message.tool_calls or [])
                            ] if getattr(resp.choices[0].message, "tool_calls", None) else None,
                        }
                    }
                ]
            }

        return resp.choices[0].message.content or ""
