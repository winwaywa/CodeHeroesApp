# app/chat_conversasion.py
from __future__ import annotations
import json
from typing import Dict, List, Tuple, Any, Optional

from chat.chat_message import ChatMessage
from chat.llm.chat_client import ChatClient
from chat.tools import TOOLS
from config.logging import logger
from retriever.pinecone.rule.rule_retriever import PineconeRuleRetriever
from stores.session_state_store import SessionState, SessionStateStore
from utils.markdown import extract_code_block

from chat.prompts import build_rule_answer_prompt
from chat.prompts import build_fix_prompt, build_summary_prompt, build_system_context
from utils.tokens import count_tokens_tiktoken

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

def _build_messages_with_budget(
    *,
    base_messages: ChatMessage,
    chat_history: List[Dict[str, str]],
    new_user_text: str,
    model: str,
    max_turns: int = 10,
    max_tokens: int = 8000,
) -> List[ChatMessage]:
    """
    Lấy tối đa max_turns lượt chat gần nhất + base_messages + user request mới nhất.
    Nếu tổng token > max_tokens, ta giảm dần số lượt cho đến khi phù hợp.
    """
    # Chuẩn hóa lịch sử chat thành ChatMessage list
    history_msgs = [ChatMessage(m["role"], m["content"]) for m in chat_history]

    # Tin nhắn người dùng mới
    new_user_msg = ChatMessage("user", new_user_text)

    # Thử lấy từ 10 → 0 lượt gần nhất
    for keep in range(max_turns, -1, -1):
        trial_messages = [base_messages] + history_msgs[-keep:] + [new_user_msg]
        token_count = count_tokens_tiktoken(trial_messages, model)
        logger.info(f"[chat] Thử build messages với {keep} lượt gần nhất: {token_count} tokens")
        if token_count <= max_tokens:
            return trial_messages  # cùng model, đủ token → dùng ngay

    # Quá giới hạn: chỉ dùng base + user
    return [base_messages] + [new_user_msg]

class ChatConversation:
    def __init__(self, *, client: ChatClient, state_store: SessionStateStore):
        self.client = client
        self.state_store = state_store
        self.rule_retriever = PineconeRuleRetriever(
            index_name="code-rules"
        )

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

    def _handle_fix_code(
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
                temperature=0.1,
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
    
    def _answer_with_rules(
        self, *, model: str, question: str, rule_snippets: list[dict]
    ) -> str:
        """Gọi LLM để trả lời câu hỏi dựa trên RULES + QUESTION. Trả về chuỗi trả lời."""
        logger.info("[chat] 🧠 Gọi LLM để trả lời dựa trên RULES (context-grounded)")

        prompt = build_rule_answer_prompt(question=question, rule_snippets=rule_snippets)
        messages = [
            ChatMessage("system", prompt["system"]),
            ChatMessage("user", prompt["user"]),
        ]
        logger.info(f"[chat] Messages LLM (answer-with-rules):\n{_format_chat_messages(messages)}")

        try:
            reply = self.client.chat_completion(
                model=model,
                messages=messages,
                temperature=0.1,
            ) or ""
            return reply.strip()
        except Exception as e:
            logger.exception(f"[chat] ❌ Lỗi LLM khi trả lời dựa trên RULES: {e}")
            return "Hiện mình không thể trả lời dựa trên tài liệu. Bạn có muốn mình sửa code luôn không?"

    def _handle_search_rule(self, *, args: dict, language: str, question: str, model: str) -> str:
        query = (args.get("query") or question or "").strip()
        lang = (args.get("language") or language or "").strip()
        if not query or not lang:
            return "Thiếu từ khóa hoặc ngôn ngữ để tìm rule."

        # 1) Gọi retriever
        res = self.rule_retriever.search(query=query, language=lang, k=6, score_threshold=0.25)

        if res.hits == 0:
            return "Không tìm thấy rule phù hợp với yêu cầu của bạn !"

        # 2) Tóm tắt bằng LLM
        return self._answer_with_rules(
            model=model,
            question=question,
            rule_snippets=[s.__dict__ for s in res.snippets],
        )
        
    def _call_llm_with_tools(
        self,
        *, model: str, base_messages: ChatMessage, chat_history: List[Dict[str, str]], question: str
    ) -> Dict[str, Any]:
        """ Gọi LLM với tool hỗ trợ, trả về raw response từ LLM. """
        logger.info("[chat] Gọi LLM với tool hỗ trợ")

        messages = _build_messages_with_budget(
            base_messages=base_messages,        # list[ChatMessage] (system + context)
            chat_history=chat_history,      # list[dict] [{role, content}]
            new_user_text=question,
            model=model,                    # tên model đang dùng
            max_turns=10,                   # tối đa 10 lượt gần nhất
            max_tokens=8000,                # giới hạn model (8k, 16k, 128k...)
        )

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
        base_msgs = ChatMessage("system", system_context)

        # Gọi LLM với tool hỗ trợ
        try:
            raw = self._call_llm_with_tools(
                model=model, base_messages=base_msgs, chat_history=chat_history, question=question
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
            tc = tool_calls[0] or {}
            fn = (tc.get("function") or {})
            name = (fn.get("name") or "").strip()
            args_raw = fn.get("arguments")
            args = _safe_json_parse(args_raw) if not isinstance(args_raw, dict) else (args_raw or {})

            if name == "search_rule":
                reply = self._handle_search_rule(args=args, language=language, question=question, model=model)
                return (reply, state, False)

            if name == "run_fix":
                base_code = (latest_fixed or origin_code or "").strip()
                if not base_code:
                    return None, "⚠️ Chưa có code để sửa. Hãy dán code hoặc yêu cầu review trước."
                raw_ins = args.get("fix_instructions", question)
                if isinstance(raw_ins, (list, tuple)):
                    raw_ins = "\n".join(map(str, raw_ins))
                elif not isinstance(raw_ins, str):
                    raw_ins = str(raw_ins or "")
                fix_instructions = raw_ins.strip()

                fixed_code, reply_msg = self._handle_fix_code(
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
