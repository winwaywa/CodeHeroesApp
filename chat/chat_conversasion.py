# app/chat_conversasion.py
from __future__ import annotations
import json
from typing import Dict, List, Tuple, Any

from chat.chat_message import ChatMessage
from chat.llm.chat_client import ChatClient
from stores.session_state_store import SessionState, SessionStateStore
from utils.markdown import extract_code_block

SYSTEM_CHAT = (
    "Bạn là trợ lý review/fix code. Trả lời ngắn gọn, rõ ràng, bằng tiếng Việt.\n"
    "- Khi người dùng yêu cầu giải thích/đánh giá (review) code: trả lời trực tiếp dựa trên ngữ cảnh, KHÔNG dùng tool.\n"
    "- Khi người dùng yêu cầu sửa/refactor/điều chỉnh code: hãy gọi function `run_fix` với tham số fix_instructions.\n"
    "Fix phải áp dụng lên phiên bản code hiện tại (ưu tiên bản đã sửa gần nhất) và tôn trọng yêu cầu của người dùng.\n"
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_fix",
            "description": "Sửa/refactor code theo yêu cầu hiện tại của người dùng.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fix_instructions": {
                        "type": "string",
                        "description": "Hướng dẫn fix cụ thể user vừa nêu (ví dụ: PEP8, thêm type hints, chuyển async, tối ưu hiệu năng…).",
                    }
                },
                "required": ["fix_instructions"],
            },
        },
    },
]

def _shorten(s: str, limit: int = 4000) -> str:
    s = s or ""
    return s if len(s) <= limit else (s[:limit] + "\n...")

class ChatConversation:
    """
    Gom toàn bộ logic chat + run_fix vào đây.
    Không dùng CodeReviewService nữa; gọi trực tiếp ChatClient.
    """
    def __init__(self, *, client: ChatClient, state_store: SessionStateStore):
        self.client = client
        self.state_store = state_store

    # --- Thực thi FIX trực tiếp (không cần service trung gian) ---
    def _exec_fix_on_current_code(
        self, *, model: str, language_fallback: str, fix_instructions: str, panel_code: str
    ) -> Tuple[SessionState, str]:
        state = self.state_store.get()
        base_code = (state.fixed_code or state.code or panel_code or "").strip()
        if not base_code:
            return state, "⚠️ Chưa có code để sửa. Hãy dán code hoặc yêu cầu review trước."

        lang = (state.language or language_fallback or "text").strip() or "text"
        review_summary = state.review_md or ""

        # Prompt fix (tự cung cấp, thay cho infra.llm.prompts)
        system_fix = (
            "Bạn là trợ lý chỉnh sửa code. Hãy tạo bản sửa cuối cùng, bọc toàn bộ trong 1 code block."
            " Nếu cần diễn giải, để sau code block ngắn gọn."
        )
        user_fix = (
            f"Ngôn ngữ: {lang}\n"
            f"Yêu cầu fix: {fix_instructions}\n"
            f"Tóm tắt review gần nhất (tuỳ chọn):\n{review_summary}\n\n"
            f"--- CODE HIỆN TẠI ---\n```\n{_shorten(base_code, 7000)}\n```"
        )

        messages = [
            ChatMessage("system", system_fix),
            ChatMessage("user", user_fix),
        ]
        fixed_md = self.client.chat_completion(
            model=model,
            messages=messages,
            temperature=0.2,
        )

        fixed_code, _ = extract_code_block(fixed_md)
        # Cập nhật state
        state.code = base_code
        state.language = lang
        state.fixed_code = (fixed_code or fixed_md).strip()
        self.state_store.set(state)

        if not state.fixed_code:
            return state, "❌ Không tạo được bản sửa. Hãy mô tả rõ hơn yêu cầu fix (ví dụ: 'theo PEP8, thêm type hints, giữ nguyên logic')."
        return state, "✅ Đã tạo bản sửa theo yêu cầu. Xem panel để copy hoặc tải file."

    # --- Gọi LLM với tools (để tự động chọn review vs fix) ---
    def _call_llm_with_tools(
        self,
        *,
        model: str,
        base_messages: List[ChatMessage],
        chat_history: List[Dict[str, str]],
        user_text: str,
    ) -> Dict[str, Any]:
        messages = base_messages + [ChatMessage(m["role"], m["content"]) for m in chat_history]
        messages.append(ChatMessage("user", user_text))
        raw = self.client.chat_completion(
            model=model,
            messages=messages,
            temperature=0.3,
            tools=TOOLS,
            tool_choice="auto",
            return_raw=True,
        )
        return raw

    # --- API chính cho UI ---
    def reply(
        self,
        *,
        question: str,
        model: str,
        chat_history: List[Dict[str, str]],
        code: str,
        language: str,
    ) -> Tuple[str, SessionState, bool]:
        """
        Trả về: (assistant_reply, new_state, did_handle_tool)
        """
        state = self.state_store.get()
        self.state_store.set(state)

        snippet_panel = (code or "").strip()
        snippet_fixed = (state.fixed_code or "").strip()
        snippet_current = snippet_fixed or (state.code or "").strip() or snippet_panel

        context_lines = [
            f"Ngôn ngữ panel: {language or 'text'}",
            f"Có review gần nhất?: {'có' if state.has_review else 'không'}",
            f"Có fixed_code hiện tại?: {'có' if bool(state.fixed_code.strip()) else 'không'}",
        ]
        system_context = (
            "Ngữ cảnh hiện có:\n"
            + "\n".join(f"- {ln}" for ln in context_lines)
            + "\n\n--- Code hiện tại (ưu tiên bản đã fix, nếu chưa có dùng bản đang có) ---\n"
            + ("```\n" + _shorten(snippet_current) + "\n```" if snippet_current else "(chưa có)")
            + "\n--- Code ở panel (nếu có) ---\n"
            + ("```\n" + _shorten(snippet_panel) + "\n```" if snippet_panel else "(chưa có)")
            + ("\n--- Tóm tắt review gần nhất ---\n" + _shorten(state.review_md) if state.review_md else "")
            + "\n\nHãy chỉ gọi tool `run_fix` khi người dùng muốn sửa/refactor/điều chỉnh code."
        )

        base_msgs = [
            ChatMessage("system", SYSTEM_CHAT),
            ChatMessage("system", system_context),
        ]

        try:
            raw = self._call_llm_with_tools(
                model=model,
                base_messages=base_msgs,
                chat_history=chat_history,
                user_text=question,
            )
        except Exception:
            return ("Không thể kết nối model. Kiểm tra cấu hình Provider/API key.", state, False)

        choice = raw.get("choices", [{}])[0]
        msg = (choice.get("message") or {})
        tool_calls = msg.get("tool_calls")

        if not tool_calls:
            content = msg.get("content") or "Bạn muốn mình giải thích/đánh giá phần nào của code?"
            return (content, state, False)

        tc = tool_calls[0]
        fn = (tc.get("function") or {})
        name = fn.get("name")
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except Exception:
            args = {}

        if name != "run_fix":
            content = msg.get("content") or "Mình chưa rõ yêu cầu. Bạn có muốn mình sửa code không?"
            return (content, state, False)

        fix_instructions = (args.get("fix_instructions") or question or "").strip()
        new_state, fix_reply = self._exec_fix_on_current_code(
            model=model,
            language_fallback=language or "text",
            fix_instructions=fix_instructions,
            panel_code=code or "",
        )
        return (fix_reply, new_state, True)
