from typing import Protocol, List, Tuple, Dict, Optional, Any

from chat.chat_message import ChatMessage

class ChatClient(Protocol):
    def chat_completion(
        self,
        *,
        model: str,
        messages: List[ChatMessage],
        temperature: float = 0.3,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,  # "auto" | {"type":"function","function":{"name":...}}
        return_raw: bool = False,           # True -> trả về dict gốc của SDK
    ) -> Any: ...                          # str (không tools) | dict (khi return_raw=True)


