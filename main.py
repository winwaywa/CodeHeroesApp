from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import streamlit as st

from config.settings import settings
from infra.factories.code_review_factory import build_code_review_service
from utils.language import guess_lang_from_code
from utils.markdown import extract_code_block
from domain.models import EXT_MAP
from domain.ports import ChatMessage

# --- App constants ---

APP_TITLE = "Code Heroes"
LANGUAGE_OPTIONS = [
    "(Chọn ngôn ngữ)",
    "python",
    "javascript",
    "typescript",
    "java",
    "csharp",
    "cpp",
    "go",
    "rust",
    "php",
    "ruby",
    "swift",
    "kotlin",
    "bash",
    "sql",
    "html",
    "css",
    "json",
    "yaml",
    "text",
]
UNKNOWN_LANGUAGE_LABEL = LANGUAGE_OPTIONS[0]
OPENAI_MODELS = ["gpt-4o-mini", "gpt-4.1-mini", "o4-mini"]
PROVIDER_OPTIONS = ["OpenAI", "Azure OpenAI"]
LANGUAGE_SELECT_KEY = "paste_lang_value"
LANGUAGE_AUTO_KEY = "paste_lang_auto"
SESSION_DEFAULTS = {
    "last_code": "",
    "last_lang": "text",
    "last_review_md": "",
    "fixed_code_block": "",
    "draft_code_input": "",
    "draft_language_input": "text",
    LANGUAGE_SELECT_KEY: UNKNOWN_LANGUAGE_LABEL,
    LANGUAGE_AUTO_KEY: True,
}
REVIEW_TOOL_TRIGGER = "/review"
FIX_TOOL_TRIGGER = "/fix"

ChatEntry = Dict[str, str]
ChatHistory = List[ChatEntry]

@dataclass(frozen=True)
class ChatTool:
    command: str
    description: str


CHAT_TOOLS: Tuple[ChatTool, ...] = (
    ChatTool(REVIEW_TOOL_TRIGGER, "Chạy review cho đoạn code ở panel chính."),
    ChatTool(FIX_TOOL_TRIGGER, "Sinh bản sửa dựa trên review gần nhất."),
)

TOOL_HINT = " | ".join(f"`{tool.command}`: {tool.description}" for tool in CHAT_TOOLS)

DEFAULT_CHAT_GREETING: ChatEntry = {
    "role": "assistant",
    "content": (
        f"Xin chào! {TOOL_HINT}. Sau đó bạn có thể hỏi thêm các câu hỏi về kết quả."
    ),
}


@dataclass(frozen=True)
class SidebarConfig:
    provider: str
    model: str
    api_key: str
    azure_api_base: str = ""
    azure_api_version: str = ""


@dataclass
class ReviewInputs:
    code_text: str
    language: str

    @property
    def active_code(self) -> str:
        return self.code_text if self.code_text.strip() else ""

    @property
    def has_code(self) -> bool:
        return bool(self.active_code)


@dataclass
class ReviewState:
    code: str = ""
    language: str = "text"
    review_md: str = ""
    fixed_code: str = ""

    @classmethod
    def from_session(cls) -> "ReviewState":
        session = st.session_state
        return cls(
            code=session.get("last_code", ""),
            language=session.get("last_lang", "text"),
            review_md=session.get("last_review_md", ""),
            fixed_code=session.get("fixed_code_block", ""),
        )

    def persist(self) -> None:
        st.session_state.last_code = self.code
        st.session_state.last_lang = self.language
        st.session_state.last_review_md = self.review_md
        st.session_state.fixed_code_block = self.fixed_code

    def with_review(self, *, code: str, language: str, review_md: str) -> "ReviewState":
        return ReviewState(code=code, language=language, review_md=review_md, fixed_code="")

    def with_fixed_code(self, fixed_code: str) -> "ReviewState":
        return ReviewState(code=self.code, language=self.language, review_md=self.review_md, fixed_code=fixed_code)

    @property
    def has_review(self) -> bool:
        return bool(self.review_md.strip())

    @property
    def has_fixed_code(self) -> bool:
        return bool(self.fixed_code.strip())


# --- Streamlit setup & state ---


def init_page() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="🛠️", layout="wide")
    st.title("🛠️" + APP_TITLE)
    st.caption("Dán code và nhận gợi ý review → fix.")


def init_session_state() -> None:
    for key, value in SESSION_DEFAULTS.items():
        st.session_state.setdefault(key, value)
    st.session_state.setdefault("chat_messages", new_chat_history())


def new_chat_history() -> ChatHistory:
    return [DEFAULT_CHAT_GREETING.copy()]


def get_chat_history() -> ChatHistory:
    return st.session_state.setdefault("chat_messages", new_chat_history())


# --- Utility helpers ---


def trigger_rerun() -> None:
    rerun = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
    if rerun is None:  # pragma: no cover - defensive branch
        raise AttributeError("Streamlit không hỗ trợ rerun trong phiên bản hiện tại.")
    rerun()


# --- Sidebar UI ---


def render_openai_config(provider: str) -> SidebarConfig:
    api_key = st.text_input(
        "OpenAI API Key",
        type="password",
        help="Hoặc đặt OPENAI_API_KEY.",
        value=settings.OPENAI_API_KEY,
    )
    model = st.selectbox("Model (OpenAI)", OPENAI_MODELS, index=0)
    return SidebarConfig(provider=provider, api_key=api_key, model=model)


def render_azure_config(provider: str) -> SidebarConfig:
    azure_api_base = st.text_input(
        "Azure API Base",
        placeholder="https://<resource>.openai.azure.com",
        value=settings.AZURE_OPENAI_API_BASE,
    )
    azure_api_version = st.text_input("Azure API Version", value=settings.AZURE_OPENAI_API_VERSION)
    api_key = st.text_input("Azure API Key", type="password", help="Hoặc AZURE_OPENAI_API_KEY.")
    model = st.text_input(
        "Deployment name (Azure)",
        placeholder="vd: gpt-4o-mini-deploy",
        value=settings.AZURE_OPENAI_DEPLOYMENT,
    )
    return SidebarConfig(
        provider=provider,
        api_key=api_key,
        model=model,
        azure_api_base=azure_api_base,
        azure_api_version=azure_api_version,
    )


def render_sidebar_settings(tab) -> SidebarConfig:
    with tab:
        provider = st.selectbox(label="Provider", options=PROVIDER_OPTIONS, index=1)
        sidebar_config = render_openai_config(provider) if provider == "OpenAI" else render_azure_config(provider)

        with st.expander("ℹ️ Notes"):
            st.markdown(
                """
                - App **không lưu** API key hay source code; mọi thứ ở trong **phiên làm việc hiện tại**.
                """
            )
    return sidebar_config


def render_sidebar() -> Tuple[SidebarConfig, object]:
    with st.sidebar:
        settings_tab, chat_tab = st.tabs(["⚙️ Settings", "💬 Chatbot"])
        sidebar_state = render_sidebar_settings(settings_tab)
    return sidebar_state, chat_tab


# --- Review workflow ---


def pick_language(code_text: str) -> Optional[str]:
    stripped_code = code_text.strip()
    detected_lang = guess_lang_from_code(stripped_code) if stripped_code else None
    if detected_lang not in LANGUAGE_OPTIONS:
        detected_lang = None

    if st.session_state.get(LANGUAGE_AUTO_KEY, True):
        st.session_state[LANGUAGE_SELECT_KEY] = detected_lang or UNKNOWN_LANGUAGE_LABEL

    selected = st.selectbox("Ngôn ngữ", LANGUAGE_OPTIONS, key=LANGUAGE_SELECT_KEY)

    st.session_state[LANGUAGE_AUTO_KEY] = (
        (detected_lang is None and selected == UNKNOWN_LANGUAGE_LABEL)
        or (detected_lang is not None and selected == detected_lang)
    )

    return None if selected == UNKNOWN_LANGUAGE_LABEL else selected


def build_review_service(cfg: SidebarConfig):
    if cfg.provider == "OpenAI":
        return build_code_review_service(
            cfg.provider,
            cfg.api_key or settings.OPENAI_API_KEY,
            cfg.model,
        )
    return build_code_review_service(
        cfg.provider,
        cfg.api_key or settings.AZURE_OPENAI_API_KEY,
        cfg.model,
        azure_api_base=cfg.azure_api_base or settings.AZURE_OPENAI_API_BASE,
        azure_api_version=cfg.azure_api_version or settings.AZURE_OPENAI_API_VERSION,
    )


def perform_review(service, cfg: SidebarConfig, inputs: ReviewInputs) -> Optional[str]:
    try:
        with st.status("Đang review …", expanded=True) as status:
            st.write("Provider:", cfg.provider)
            st.write("Model / Deployment:", cfg.model)
            st.write("Language:", inputs.language)
            review_md = service.review(language=inputs.language, code=inputs.active_code)
            status.update(label="✅ Review xong", state="complete")
        return review_md
    except Exception as exc:  # pragma: no cover - streamlit UI
        st.exception(exc)
        return None


def perform_fix(service, state: ReviewState) -> Optional[str]:
    try:
        with st.status("Đang tạo bản sửa…", expanded=True) as status:
            fixed_md = service.fix(
                language=state.language,
                code=state.code,
                review_summary=state.review_md,
            )
            status.update(label="✅ Đã tạo bản sửa", state="complete")
    except Exception as exc:  # pragma: no cover - streamlit UI
        st.exception(exc)
        return None

    fixed_code, _ = extract_code_block(fixed_md)
    return (fixed_code or fixed_md).strip()


def render_review_results(state: ReviewState) -> None:
    if not state.has_review:
        return

    st.subheader("📋 Kết quả Review")
    st.markdown(state.review_md)

    if not state.has_fixed_code:
        st.caption(f"Gõ `{FIX_TOOL_TRIGGER}` trong chatbot để tạo bản sửa.")

    if state.has_fixed_code:
        st.subheader("✅ Code đã Fix ")
        st.code(state.fixed_code, language=state.language or "text")
        download_name = "fixed_code" + EXT_MAP.get(state.language, ".txt")
        st.download_button(
            "⬇️ Tải code đã fix",
            data=state.fixed_code.encode("utf-8"),
            file_name=download_name,
            mime="text/plain",
            use_container_width=True,
        )


def handle_tool_invocation(
    prompt: str,
    service,
    cfg: SidebarConfig,
    review_state: ReviewState,
) -> Tuple[bool, ReviewState, str]:
    command = prompt.strip().split()[0].lower()
    if command == REVIEW_TOOL_TRIGGER:
        code_text = st.session_state.get("draft_code_input", "")
        language = st.session_state.get("draft_language_input", "text")
        inputs = ReviewInputs(code_text=code_text, language=language or "text")
        if not inputs.has_code:
            return True, review_state, "⚠️ Không tìm thấy code để review. Hãy dán code vào ô bên trái nhé!"

        review_md = perform_review(service, cfg, inputs)
        if not review_md:
            return True, review_state, "❌ Review không thành công. Kiểm tra lại cấu hình và thử lại."

        new_state = review_state.with_review(
            code=inputs.active_code,
            language=inputs.language,
            review_md=review_md,
        )
        new_state.persist()
        return True, new_state, "✅ Đã review code. Bạn có thể xem kết quả và tải bản báo cáo ở panel chính."

    if command == FIX_TOOL_TRIGGER:
        if not review_state.has_review:
            return (
                True,
                review_state,
                f"⚠️ Chưa có kết quả review. Hãy chạy `{REVIEW_TOOL_TRIGGER}` trước khi yêu cầu fix.",
            )

        fixed_code = perform_fix(service, review_state)
        if not fixed_code:
            return True, review_state, "❌ Không tạo được bản sửa. Thử lại sau hoặc kiểm tra cấu hình."

        new_state = review_state.with_fixed_code(fixed_code)
        new_state.persist()
        return True, new_state, "✅ Đã tạo bản sửa. Xem panel chính để copy hoặc tải file."

    return False, review_state, ""


# --- Layout helpers ---


def render_primary_panel(
    review_service,
    sidebar_cfg: SidebarConfig,
    state: ReviewState,
) -> Tuple[ReviewState, str]:
    code_text = st.text_area("Your code", height=280, placeholder="Paste your code…")
    st.session_state.draft_code_input = code_text

    language = pick_language(code_text) or "text"
    st.session_state.draft_language_input = language

    render_review_results(state)

    if not state.has_review:
        st.caption(f"Sử dụng chatbot với lệnh `{REVIEW_TOOL_TRIGGER}` để chạy đánh giá code.")

    active_language = state.language if state.has_review else language

    return state, active_language


# --- Chatbot helpers ---


def request_chatbot_reply(
    service,
    cfg: SidebarConfig,
    review_state: ReviewState,
    fallback_language: str,
    question: str,
) -> str:
    client = getattr(service, "client", None)
    chat_history = get_chat_history()
    language_context = review_state.language or fallback_language or "text"
    review_summary = review_state.review_md.strip()
    code_under_review = review_state.code.strip() or "(người dùng chưa cung cấp)"

    base_messages = [
        ChatMessage(
            "system",
            "Bạn là trợ lý review code. Giữ câu trả lời ngắn gọn, tập trung vào vấn đề kỹ thuật, "
            "và trả lời bằng tiếng Việt. Nếu người dùng hỏi ngoài phạm vi code review, hãy nhẹ nhàng hướng họ quay lại. "
            f"Nhắc người dùng rằng họ có thể dùng `{REVIEW_TOOL_TRIGGER}` để chạy đánh giá code "
            f"và `{FIX_TOOL_TRIGGER}` để tạo bản sửa.",
        ),
        ChatMessage(
            "system",
            f"Mô tả review gần nhất:\n{review_summary}\n\n"
            f"Ngôn ngữ code: {language_context}\n"
            f"Đoạn code đang xét:\n{code_under_review}",
        ),
    ]
    payload = base_messages + [ChatMessage(role=msg["role"], content=msg["content"]) for msg in chat_history]
    payload.append(ChatMessage("user", question))

    if client is None:
        return "Hiện tại tôi không thể kết nối tới AI, nhưng bạn vẫn có thể ghi chú lại câu hỏi tại đây."

    try:
        return client.chat_completion(
            model=cfg.model,
            messages=payload,
            temperature=0.3,
        )
    except Exception:  # pragma: no cover - network call
        return (
            "Không thể gọi tới model ngay lúc này. "
            "Bạn hãy thử lại sau hoặc kiểm tra lại cấu hình Provider/API key."
        )


def render_chatbot_panel(
    service,
    cfg: SidebarConfig,
    active_lang: str,
    review_state: ReviewState,
) -> ReviewState:
    prompt = st.chat_input("Đặt câu hỏi tiếp theo…", key="chatbot_prompt")
    chat_history = get_chat_history()

    messages_container = st.container(height=420, border=True)
    with messages_container:
        for message in chat_history:
            role = message["role"]
            with st.chat_message(role):
                st.markdown(message["content"])

        if prompt:
            chat_history.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            handled, updated_state, tool_reply = handle_tool_invocation(
                prompt,
                service=service,
                cfg=cfg,
                review_state=review_state,
            )
            review_state = updated_state

            if handled:
                with st.chat_message("assistant"):
                    st.markdown(tool_reply)
                chat_history.append({"role": "assistant", "content": tool_reply})
                st.session_state.chat_messages = chat_history
                trigger_rerun()

            with st.chat_message("assistant"):
                with st.spinner("Đang soạn câu trả lời…"):
                    reply = request_chatbot_reply(
                        service,
                        cfg=cfg,
                        review_state=review_state,
                        fallback_language=active_lang,
                        question=prompt,
                    )
                st.markdown(reply)
            chat_history.append({"role": "assistant", "content": reply})

    return review_state

# --- Entry point ---


def main():
    init_page()
    init_session_state()
    sidebar_cfg, chat_container = render_sidebar()
    review_service = build_review_service(sidebar_cfg)

    review_state = ReviewState.from_session()
    review_state, active_chat_language = render_primary_panel(review_service, sidebar_cfg, review_state)

    with chat_container:
        review_state = render_chatbot_panel(
            review_service,
            sidebar_cfg,
            active_lang=active_chat_language,
            review_state=review_state,
        )


if __name__ == "__main__":
    main()
