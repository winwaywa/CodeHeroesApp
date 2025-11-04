# app/chat_conversasion.py
from __future__ import annotations
import json
from typing import Dict, List, Tuple, Any, Optional

from chat.chat_message import ChatMessage
from chat.llm.chat_client import ChatClient
from config.logging import logger
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

def _safe_json_parse(s: Optional[str]) -> Dict[str, Any]:
    if not s:
        return {}
    try:
        return json.loads(s)
    except Exception as e:
        logger.warning(f"[chat] JSON parse error on tool arguments: {e}; raw={s!r}")
        return {}

class ChatConversation:
    """
    Gom toàn bộ logic chat + run_fix vào đây.
    """
    def __init__(self, *, client: ChatClient, state_store: SessionStateStore):
        self.client = client
        self.state_store = state_store

    # Thêm helper: tóm tắt thay đổi giữa base_code và fixed_code (KHÔNG dùng regex)
    def _summarize_changes(
        self, *, model: str, language: str, base_code: str, fixed_code: str
    ) -> str:
        """
        Dùng LLM để so sánh base_code và fixed_code rồi liệt kê thay đổi.
        Yêu cầu LLM trả về bullet ngắn gọn (không code block / không preamble).
        """
        system_sum = (
            "Bạn là reviewer giàu kinh nghiệm. Hãy so sánh hai phiên bản code và "
            "liệt kê thay đổi một cách ngắn gọn, bằng tiếng Việt, dùng gạch đầu dòng '- '. "
            "KHÔNG chèn code block, KHÔNG mở đầu dài dòng. Tối đa 5 bullet."
        )
        user_sum = (
            f"Ngôn ngữ: {language}\n"
            f"--- ORIGINAL ---\n```\n{base_code}\n```\n"
            f"--- FIXED ---\n```\n{fixed_code}\n```"
        )
        try:
            summary = self.client.chat_completion(
                model=model,
                messages=[ChatMessage("system", system_sum), ChatMessage("user", user_sum)],
                temperature=0.1,
            )
            return (summary or "").strip()
        except Exception as e:
            logger.exception(f"[chat] _summarize_changes: LLM error: {e}")
            return ""


    # Thực thi FIX trực tiếp (2-call: 1) lấy code đã fix, 2) tóm tắt thay đổi)
    def _exec_fix_on_current_code(
        self, *,
        model: str,
        language: str,
        base_code: str,
        fix_instructions: str,
    ) -> Tuple[Optional[str], str]:
        """
        Nhận dữ liệu từ bên ngoài, không gọi state_store.
        Trả về:
        - fixed_code: Optional[str]
        - short_msg: str (nội dung động do LLM tóm tắt thay đổi)
        """
        logger.info("[chat] _exec_fix_on_current_code: start")
        logger.debug(f"[chat] fix_instructions={fix_instructions!r}")

        bc = (base_code or "").strip()
        if not bc:
            logger.info("[chat] _exec_fix_on_current_code: no base code")
            return None, "⚠️ Chưa có code để sửa. Hãy dán code hoặc yêu cầu review trước."

        # Call 1: YÊU CẦU TRẢ VỀ CHỈ CODE (một code block, không kèm giải thích)
        system_fix = (
            "Bạn là trợ lý chỉnh sửa code. Hãy trả về CHỈ MỘT code block duy nhất chứa phiên bản đã sửa, "
            "KHÔNG kèm bất kỳ giải thích hay văn bản nào khác. Không được chèn code block thứ hai."
        )
        user_fix = (
            f"Ngôn ngữ: {language}\n"
            f"Yêu cầu fix: {fix_instructions}\n"
            f"--- CODE HIỆN TẠI ---\n```\n{bc}\n```"
        )

        try:
            fixed_md = self.client.chat_completion(
                model=model,
                messages=[ChatMessage("system", system_fix), ChatMessage("user", user_fix)],
                temperature=0.2,
            )
        except Exception as e:
            logger.exception(f"[chat] _exec_fix_on_current_code: LLM error (fix): {e}")
            return None, "Không thể kết nối model để chạy fix. Kiểm tra cấu hình Provider/API key."

        # Lấy code từ code block (nếu model tuân thủ thì fixed_md chính là code block)
        fixed_code, _ = extract_code_block(fixed_md)
        final_code = (fixed_code or fixed_md or "").strip()

        if not final_code:
            logger.info("[chat] _exec_fix_on_current_code: empty fixed_code after LLM")
            return None, (
                "❌ Không tạo được bản sửa. Hãy mô tả rõ hơn yêu cầu fix "
                "(ví dụ: 'theo PEP8, thêm type hints, giữ nguyên logic')."
            )

        # Call 2: Tạo summary động về thay đổi (KHÔNG dùng regex)
        summary = self._summarize_changes(
            model=model, language=language, base_code=bc, fixed_code=final_code
        )

        if summary:
            short_msg = "✅ Tôi đã fix:\n" + "\n".join(
                f"- {line.lstrip('- ').strip()}" for line in summary.splitlines() if line.strip()
            )
        else:
            # Fallback khi LLM tóm tắt gặp lỗi
            short_msg = "✅ Đã áp dụng yêu cầu fix và cập nhật bản sửa trong panel."

        logger.info("[chat] _exec_fix_on_current_code: done, fixed_code generated + summary built")
        logger.debug(f"[chat] _exec_fix_on_current_code: summary_preview={summary[:200]!r}")
        return final_code, short_msg


    # --- Gọi LLM (cho phép tool) ---
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
        logger.info("[chat] _call_llm_with_tools: sending to LLM")
        try:
            raw = self.client.chat_completion(
                model=model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                return_raw=True,
            )
        except Exception as e:
            logger.exception(f"[chat] _call_llm_with_tools: LLM error: {e}")
            raise
        return raw or {}

    # --- API chính cho UI ---
    def reply(
        self,
        *,
        question: str
    ) -> Tuple[str, SessionState, bool]:
        """
        Trả:
          - message_to_user: str
          - used_tool: bool
        """
        state = self.state_store.get()

        model = state.model
        chat_history = state.chat_messages or []
        origin_code = state.origin_code or ""
        language = state.language or "text"
        latest_fixed = (state.fixed_code or "").strip()

        logger.info("[chat] reply: start")
        logger.info(
            "Chatbot Input:\n"
            f"  Question: {question}\n"
            f"  Model: {model}\n"
            f"  Language: {language}\n"
            f"  Code present: {bool(origin_code)}\n"
            f"  Fixed Code present: {bool(latest_fixed)}\n"
            f"  Chat History Length: {len(chat_history)}"
        )

        # System context an toàn (đóng code fence đầy đủ)
        system_context = (
            f"Source gốc người dùng nhập vào:\n```\n{origin_code}\n```\n"
            f"Ngôn ngữ: {language}\n"
        )
        if latest_fixed:
            system_context += f"Phiên bản code đã fix gần nhất:\n```\n{latest_fixed}\n```\n"

        base_msgs = [
            ChatMessage("system", SYSTEM_CHAT),
            ChatMessage("system", system_context),
        ]

        # 1) Gọi LLM cho phép quyết định dùng tool hay trả lời trực tiếp
        try:
            raw = self._call_llm_with_tools(
                model=model,
                base_messages=base_msgs,
                chat_history=chat_history,
                user_text=question,
            )
        except Exception:
            logger.info("[chat] reply: LLM not reachable")
            return ("Không thể kết nối model. Kiểm tra cấu hình Provider/API key.", state, False)

        choices = raw.get("choices") or []
        if not choices:
            logger.info("[chat] reply: empty choices from LLM")
            return ("Mình chưa nhận được phản hồi từ model. Bạn thử hỏi lại nhé.", state, False)

        message: Dict[str, Any] = (choices[0].get("message") or {})
        content: str = (message.get("content") or "").strip()
        tool_calls = message.get("tool_calls") or []

        logger.info(f"[chat] reply: tool_calls_detected={bool(tool_calls)}")
        if tool_calls:
            # 2) Có tool-call -> chỉ xử lý tool đầu tiên theo quy ước
            first_tc = tool_calls[0] or {}
            fn = (first_tc.get("function") or {})
            name = (fn.get("name") or "").strip()
            args_raw = fn.get("arguments")
            args = _safe_json_parse(args_raw) if not isinstance(args_raw, dict) else (args_raw or {})

            logger.info(f"[chat] reply: tool={name}, args={args}")
            if name != "run_fix":
                fallback = content or "Mình chưa rõ yêu cầu. Bạn có muốn mình sửa code không?"
                logger.info("[chat] reply: unexpected tool name, fallback message returned")
                return (fallback, state, False)

            # Chuẩn bị dữ liệu truyền vào _exec_fix_on_current_code
            base_code = (latest_fixed or origin_code or "").strip()
            fix_instructions = (args.get("fix_instructions") or question or "").strip()

            fixed_code, reply_msg = self._exec_fix_on_current_code(
                model=model,
                language=language,
                base_code=base_code,
                fix_instructions=fix_instructions,
            )

            logger.info(f"[chat] reply: fix executed, fixed_code present={fixed_code}")
            logger.debug(f"[chat] reply: short_msg={reply_msg!r}")

            # Nếu có fixed_code -> cập nhật state tại đây
            if fixed_code:
                state.fixed_code = fixed_code
                logger.info("[chat] reply: fix done, state.fixed_code updated")

            # Tạo câu trả lời cho người dùng, nêu rõ đã fix theo gì
            return (reply_msg, state, True)

        # 3) Không có tool-call -> trả lời trực tiếp cho review/giải thích
        if not content:
            content = "Bạn muốn mình giải thích/đánh giá phần nào của code?"
        logger.info("[chat] reply: no tool, returning direct answer")
        return (content, state, False)
