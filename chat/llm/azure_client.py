from typing import List, Optional, Dict, Any

from openai import AzureOpenAI
from chat.chat_message import ChatMessage
from chat.llm.chat_client import ChatClient

class AzureOpenAIChatClient(ChatClient):
    """
    Dành cho Azure OpenAI.
    - api_base: dạng https://<resource>.openai.azure.com
    - api_version: ví dụ "2024-08-01-preview"
    - model: tên deployment (vd: "gpt-4o-mini-deploy")
    """
    def __init__(self, *, api_key: str, api_base: str, api_version: str):
         self._client = AzureOpenAI(
            api_key=api_key,
            azure_endpoint=api_base,
            api_version=api_version,
        )

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
            kwargs["tool_choice"] = tool_choice

        resp = self._client.chat.completions.create(**kwargs)

        if return_raw:
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
