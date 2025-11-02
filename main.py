from dataclasses import dataclass
from typing import Dict, List, Optional

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
    "python", "javascript", "typescript", "java", "csharp", "cpp", "go", "rust",
    "php", "ruby", "swift", "kotlin", "bash", "sql", "html", "css", "json", "yaml", "text",
]
UNKNOWN_LANGUAGE_LABEL = LANGUAGE_OPTIONS[0]
LANGUAGE_SELECT_KEY = "paste_lang_value"
LANGUAGE_AUTO_KEY = "paste_lang_auto"
SESSION_DEFAULTS = {
    "last_code": "",
    "last_lang": "text",
    "last_review_md": "",
    "fixed_code_block": "",
    LANGUAGE_SELECT_KEY: UNKNOWN_LANGUAGE_LABEL,
    LANGUAGE_AUTO_KEY: True,
}

ChatEntry = Dict[str, str]
ChatHistory = List[ChatEntry]

DEFAULT_CHAT_GREETING: ChatEntry = {"role": "assistant", "content": "Hỏi tôi về kết quả review nhé! 👇"}


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


def reset_chat_history() -> None:
    st.session_state.chat_messages = new_chat_history()


# --- Sidebar UI ---

def render_sidebar_settings(tab) -> SidebarConfig:
    with tab:
        provider = st.selectbox(label="Provider", options=["OpenAI", "Azure OpenAI"], index=1)

        if provider == "OpenAI":
            api_key = st.text_input(
                "OpenAI API Key",
                type="password",
                help="Hoặc đặt OPENAI_API_KEY.",
                value=settings.OPENAI_API_KEY,
            )
            model = st.selectbox("Model (OpenAI)", ["gpt-4o-mini", "gpt-4.1-mini", "o4-mini"], index=0)
            azure_api_base = ""
            azure_api_version = ""
        else:
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

        with st.expander("ℹ️ Notes"):
            st.markdown(
                """
                - App **không lưu** API key hay source code; mọi thứ ở trong **phiên làm việc hiện tại**.
                """
            )
    return SidebarConfig(
        provider=provider,
        api_key=api_key,
        model=model,
        azure_api_base=azure_api_base,
        azure_api_version=azure_api_version,
    )


def render_sidebar():
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
            "OpenAI",
            cfg.api_key or settings.OPENAI_API_KEY,
            cfg.model,
        )
    return build_code_review_service(
        "Azure OpenAI",
        cfg.api_key or settings.AZURE_OPENAI_API_KEY,
        cfg.model,
        azure_api_base=cfg.azure_api_base or settings.AZURE_OPENAI_API_BASE,
        azure_api_version=cfg.azure_api_version or settings.AZURE_OPENAI_API_VERSION,
    )


def handle_review_and_fix(service, cfg: SidebarConfig, inputs: ReviewInputs):
    review_clicked = st.button("🔍 Review", use_container_width=True, disabled=not inputs.has_code)
    active_code = inputs.active_code
    active_lang = inputs.language

    if review_clicked:
        try:
            with st.status("Đang review …", expanded=True) as status:
                st.write("Provider:", cfg.provider)
                st.write("Model / Deployment:", cfg.model)
                st.write("Language:", active_lang)
                review_md = service.review(language=active_lang, code=active_code)
                status.update(label="✅ Review xong", state="complete")
            st.session_state.last_code = active_code
            st.session_state.last_lang = active_lang
            st.session_state.last_review_md = review_md
            st.session_state.fixed_code_block = ""
            reset_chat_history()
        except Exception as exc:
            st.exception(exc)

    if st.session_state.last_review_md:
        st.subheader("📋 Kết quả Review")
        st.markdown(st.session_state.last_review_md)

        fix_clicked = st.button("🛠️ Fix code", use_container_width=True)
        if fix_clicked:
            try:
                with st.status("Đang tạo bản sửa…", expanded=True) as status:
                    fixed_md = service.fix(
                        language=st.session_state.last_lang,
                        code=st.session_state.last_code,
                        review_summary=st.session_state.last_review_md,
                    )
                    status.update(label="✅ Đã tạo bản sửa", state="complete")
                fixed_code, _ = extract_code_block(fixed_md)
                st.session_state.fixed_code_block = (fixed_code or fixed_md).strip()
            except Exception as exc:
                st.exception(exc)

    if st.session_state.fixed_code_block:
        st.subheader("✅ Code đã Fix ")
        st.code(st.session_state.fixed_code_block, language=st.session_state.last_lang or "text")
        download_name = "fixed_code" + EXT_MAP.get(st.session_state.last_lang, ".txt")
        st.download_button(
            "⬇️ Tải code đã fix",
            data=st.session_state.fixed_code_block.encode("utf-8"),
            file_name=download_name,
            mime="text/plain",
            use_container_width=True,
        )


# --- Layout helpers ---

def render_primary_panel(review_service, sidebar_cfg: SidebarConfig):
    code_text = st.text_area("Your code", height=280, placeholder="Paste your code…")
    language = pick_language(code_text) or "text"
    inputs = ReviewInputs(code_text=code_text, language=language)

    handle_review_and_fix(review_service, sidebar_cfg, inputs)

    return st.session_state.get("last_lang") or inputs.language


# --- Chatbot helpers ---

def request_chatbot_reply(service, model: str, active_lang: str, question: str) -> str:
    client = getattr(service, "client", None)
    chat_history = get_chat_history()
    base_messages = [
        ChatMessage(
            "system",
            "Bạn là trợ lý review code. Giữ câu trả lời ngắn gọn, tập trung vào vấn đề kỹ thuật, "
            "và trả lời bằng tiếng Việt. Nếu người dùng hỏi ngoài phạm vi code review, hãy nhẹ nhàng hướng họ quay lại."
        ),
        ChatMessage(
            "system",
            f"Mô tả review gần nhất:\n{st.session_state.last_review_md.strip()}\n\n"
            f"Ngôn ngữ code: {active_lang}\n"
            f"Đoạn code đang xét:\n{st.session_state.last_code.strip() or '(người dùng chưa cung cấp)'}"
        ),
    ]
    payload = base_messages + [ChatMessage(role=msg["role"], content=msg["content"]) for msg in chat_history]
    payload.append(ChatMessage("user", question))

    if client is None:
        return "Hiện tại tôi không thể kết nối tới AI, nhưng bạn vẫn có thể ghi chú lại câu hỏi tại đây."

    try:
        return client.chat_completion(
            model=model,
            messages=payload,
            temperature=0.3,
        )
    except Exception:
        return (
            "Không thể gọi tới model ngay lúc này. "
            "Bạn hãy thử lại sau hoặc kiểm tra lại cấu hình Provider/API key."
        )


def render_chatbot_panel(service, model: str, active_lang: str):
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

            with st.chat_message("assistant"):
                with st.spinner("Đang soạn câu trả lời…"):
                    reply = request_chatbot_reply(service, model=model, active_lang=active_lang, question=prompt)
                st.markdown(reply)
            chat_history.append({"role": "assistant", "content": reply})


# --- Entry point ---

def main():
    init_page()
    init_session_state()
    sidebar_cfg, chat_container = render_sidebar()
    review_service = build_review_service(sidebar_cfg)

    active_chat_language = render_primary_panel(review_service, sidebar_cfg)

    with chat_container:
        render_chatbot_panel(
            review_service,
            sidebar_cfg.model,
            active_lang=active_chat_language,
        )


if __name__ == "__main__":
    main()
