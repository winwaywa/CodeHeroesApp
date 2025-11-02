import streamlit as st

from config.settings import settings
from infra.factories.code_review_factory import build_code_review_service
from utils.language import guess_lang_from_code
from utils.markdown import extract_code_block
from domain.models import EXT_MAP

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


def init_page() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="🛠️", layout="wide")
    st.title("🛠️" + APP_TITLE)
    st.caption("Dán code và nhận gợi ý review → fix.")


def init_session_state() -> None:
    for key, value in SESSION_DEFAULTS.items():
        st.session_state.setdefault(key, value)


def render_sidebar():
    with st.sidebar:
        st.subheader("⚙️ Settings")
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

    return {
        "provider": provider,
        "api_key": api_key,
        "model": model,
        "azure_api_base": azure_api_base,
        "azure_api_version": azure_api_version,
    }


def pick_language(code_text: str):
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


def build_review_service(sidebar_state):
    provider = sidebar_state["provider"]
    api_key = sidebar_state["api_key"]
    model = sidebar_state["model"]
    if provider == "OpenAI":
        return build_code_review_service("OpenAI", api_key or settings.OPENAI_API_KEY, model)
    return build_code_review_service(
        "Azure OpenAI",
        api_key or settings.AZURE_OPENAI_API_KEY,
        model,
        azure_api_base=sidebar_state["azure_api_base"] or settings.AZURE_OPENAI_API_BASE,
        azure_api_version=sidebar_state["azure_api_version"] or settings.AZURE_OPENAI_API_VERSION,
    )


def handle_review_and_fix(service, provider, model, active_code, active_lang):
    review_clicked = st.button("🔍 Review", use_container_width=True, disabled=(not active_code))

    if review_clicked:
        try:
            with st.status("Đang review …", expanded=True) as status:
                st.write("Provider:", provider)
                st.write("Model / Deployment:", model)
                st.write("Language:", active_lang)
                review_md = service.review(language=active_lang, code=active_code)
                status.update(label="✅ Review xong", state="complete")
            st.session_state.last_code = active_code
            st.session_state.last_lang = active_lang
            st.session_state.last_review_md = review_md
            st.session_state.fixed_code_block = ""
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


def render_notes():
    st.divider()
    with st.expander("ℹ️ Notes"):
        st.markdown(
            """
            - App hiện chỉ hỗ trợ dán trực tiếp nội dung code (text).
            - Với đoạn code dài, cân nhắc chia nhỏ để tránh giới hạn token hoặc rate-limit.
            - App **không lưu** API key hay source code; mọi thứ ở trong **phiên làm việc hiện tại**.
            """
        )


def main():
    init_page()
    sidebar_state = render_sidebar()
    init_session_state()

    code_text = st.text_area("Your code", height=280, placeholder="Paste your code…")
    selected_lang = pick_language(code_text)
    review_service = build_review_service(sidebar_state)

    active_code = code_text if code_text.strip() else ""
    active_lang = selected_lang or "text"
    handle_review_and_fix(
        review_service,
        sidebar_state["provider"],
        sidebar_state["model"],
        active_code,
        active_lang,
    )

    render_notes()


if __name__ == "__main__":
    main()
