# app/chat_conversasion.py
from __future__ import annotations
import json
from typing import Dict, List, Tuple, Any, Optional

from chat.chat_message import ChatMessage
from chat.llm.chat_client import ChatClient
from config.logging import logger
from stores.session_state_store import SessionState, SessionStateStore
from utils.markdown import extract_code_block

from chat.prompts import SYSTEM_CHAT
from chat.prompts import build_fix_prompt, build_summary_prompt, build_system_context

def _safe_json_parse(s: Optional[str]) -> Dict[str, Any]:
    if not s:
        return {}
    try:
        return json.loads(s)
    except Exception as e:
        logger.warning(f"[chat] Lỗi parse tool args: {e}")
        return {}

def _format_chat_messages(msgs: List[ChatMessage]) -> str:
    """
    Convert list ChatMessage thành string dễ đọc để log.
    Mỗi message sẽ hiển thị ở dạng:
    [role] nội dung
    """
    lines = []
    for i, msg in enumerate(msgs, start=1):
        role = msg.role
        content = msg.content.strip() if msg.content else ""
        lines.append(f"{i:02d}. [{role}] {content}")
    return "\n".join(lines)

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

class ChatConversation:
    def __init__(self, *, client: ChatClient, state_store: SessionStateStore):
        self.client = client
        self.state_store = state_store

    def _summarize_changes(
        self, *, model: str, language: str, base_code: str, fixed_code: str
    ) -> str:
        """ Gọi LLM để tóm tắt thay đổi giữa base_code và fixed_code. Trả về chuỗi tóm tắt. """
        logger.info("[chat] Gọi LLM để tóm tắt thay đổi code")

        prompt = build_summary_prompt(language=language, base_code=base_code, fixed_code=fixed_code)
        messages = [ChatMessage("system", prompt["system"]), ChatMessage("user", prompt["user"])]
        logger.info(f"[chat] Messages llm tóm tắt thay đổi: \n{_format_chat_messages(messages)}")

        try:
            return (self.client.chat_completion(
                model=model,
                messages=[ChatMessage("system", prompt["system"]), ChatMessage("user", prompt["user"])],
                temperature=0.1,
            ) or "").strip()
        except Exception as e:
            logger.exception(f"[chat] Lỗi LLM khi tóm tắt thay đổi code: {e}")
            return ""

    def _exec_fix_on_current_code(
        self, *, model: str, language: str, base_code: str, fix_instructions: str
    ) -> Tuple[Optional[str], str]:
        """ Thực hiện fix code hiện tại theo hướng dẫn, trả về (fixed_code, reply_message) """
        logger.info("[chat] Gọi LLM để fix code")

        if not (base_code or "").strip():
            return None, "⚠️ Chưa có code để sửa. Hãy dán code hoặc yêu cầu review trước."

        prompt = build_fix_prompt(language=language, base_code=base_code.strip(), fix_instructions=fix_instructions.strip())
        messages = [ChatMessage("system", prompt["system"]), ChatMessage("user", prompt["user"])]
        logger.info(f"[chat] Messages llm fix code: \n{_format_chat_messages(messages)}")

        try:
            fixed_md = self.client.chat_completion(
                model=model,
                messages=messages,
                temperature=0.2,
            )
        except Exception as e:
            logger.exception(f"[chat] Lỗi LLM khi thực hiện fix code: {e}")
            return None, "Không thể kết nối model để chạy fix. Kiểm tra cấu hình Provider/API key."

        # Extract code đã fix
        fixed_code = extract_code_block(fixed_md)
        if not fixed_code:
            return None, ("❌ Không tạo được bản sửa. Hãy mô tả rõ hơn yêu cầu fix "
                          "(ví dụ: 'theo PEP8, thêm type hints, giữ nguyên logic').")
        
        # Tóm tắt thay đổi
        summary = self._summarize_changes(model=model, language=language, base_code=base_code, fixed_code=fixed_code)
        if summary:
            reply = "✅ Tôi đã thực hiện chỉnh sửa:\n" + "\n".join(f"- {line.lstrip('- ').strip()}" for line in summary.splitlines() if line.strip())
        else:
            reply = "✅ Đã áp dụng yêu cầu chỉnh sửa và cập nhật bản sửa trong panel."

        return fixed_code, reply

    def _call_llm_with_tools(
        self,
        *, model: str, base_messages: List[ChatMessage], chat_history: List[Dict[str, str]], user_text: str
    ) -> Dict[str, Any]:
        """ Gọi LLM với tool hỗ trợ, trả về raw response từ LLM. """
        logger.info("[chat] Gọi LLM với tool hỗ trợ")

        messages = base_messages \
            # + [ChatMessage(m["role"], m["content"]) for m in chat_history]
        messages.append(ChatMessage("user", user_text))

        logger.info(f"[chat] Messages llm có tool: \n{_format_chat_messages(messages)}")

        try:
            raw = self.client.chat_completion(
                model=model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                return_raw=True,
            )
        except Exception as e:
            logger.exception(f"[chat] Lỗi gọi LLM chatbot: {e}")
            raise
        return raw or {}

    # --- API chính ---
    def reply(self, *, question: str) -> Tuple[str, SessionState, bool]:
        state = self.state_store.get()

        model = state.model
        chat_history = state.chat_messages or []
        origin_code = state.origin_code or ""
        language = state.language or "text"
        latest_fixed = (state.fixed_code or "").strip()

        # System context + system chat
        system_context = build_system_context(origin_code=origin_code, latest_fixed=latest_fixed, language=language)
        base_msgs = [ChatMessage("system", SYSTEM_CHAT), ChatMessage("system", system_context)]

        # 1) Gọi LLM
        try:
            raw = self._call_llm_with_tools(
                model=model, base_messages=base_msgs, chat_history=chat_history, user_text=question
            )
        except Exception:
            logger.info("[chat] Không kết nối được model")
            return ("Không thể kết nối model. Kiểm tra cấu hình Provider/API key.", state, False)

        choices = raw.get("choices") or []
        if not choices:
            logger.info("[chat] LLM không trả về lựa chọn")
            return ("Mình chưa nhận được phản hồi từ model. Bạn thử hỏi lại nhé.", state, False)

        message: Dict[str, Any] = (choices[0].get("message") or {})
        content: str = (message.get("content") or "").strip()
        tool_calls = message.get("tool_calls") or []

        if tool_calls:
            # parse để lấy fix_instructions
            first_tc = tool_calls[0] or {}
            fn = (first_tc.get("function") or {})
            name = (fn.get("name") or "").strip()
            args_raw = fn.get("arguments")
            args = _safe_json_parse(args_raw) if not isinstance(args_raw, dict) else (args_raw or {})
            
            if name != "run_fix":
                fallback = content or "Mình chưa rõ yêu cầu. Bạn có muốn mình sửa code không?"
                logger.info("[chat] ↩️ Trả về fallback (tool không khớp)")
                return (fallback, state, False)

            base_code = (latest_fixed or origin_code or "").strip()
            fix_instructions = (args.get("fix_instructions") or question or "").strip()

            fixed_code, reply_msg = self._exec_fix_on_current_code(
                model=model, language=language, base_code=base_code, fix_instructions=fix_instructions
            )

            # Cập nhật code đã fix vào state
            if fixed_code:
                state.fixed_code = fixed_code

            return (reply_msg, state, True)

        # Không có tool-call -> trả lời trực tiếp
        if not content:
            content = "Bạn muốn mình giải thích/đánh giá phần nào của code?"
        return (content, state, False)
