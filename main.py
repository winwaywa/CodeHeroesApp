# app/main.py
from pathlib import Path
from typing import Dict, List
import streamlit as st

from chat.llm.azure_client import AzureOpenAIChatClient
from chat.llm.openai_client import OpenAIChatClient
from config.constant import APP_TITLE, EXT_MAP, LANGUAGE_OPTIONS, OPENAI_MODELS, PROVIDER_OPTIONS
from config.env import settings
from stores.session_state_store import SessionState, SessionStateStore
from utils.code_diff import make_github_like_unified_html
from utils.language import guess_lang_from_code
from chat.chat_conversasion import ChatConversation
from config.logging import logger

# ============== Page & header ==============
st.set_page_config(page_title=APP_TITLE, page_icon="🛠️", layout="wide")
st.title("🛠️" + APP_TITLE)
st.caption("Dán code của bạn để có thể thực hiện trò chuyện.")

# ============== Sidebar ==============
with st.sidebar:
    settings_tab, chat_tab = st.tabs(["⚙️ Settings", "💬 Chatbot"])
    # Settings tab
    with settings_tab:
        provider = st.selectbox("Provider", PROVIDER_OPTIONS, index=1)
        if provider == "OpenAI":
            api_key = st.text_input(
                "OpenAI API Key", type="password", value=settings.OPENAI_API_KEY, help="Hoặc đặt OPENAI_API_KEY."
            )
            model = st.selectbox("Model (OpenAI)", OPENAI_MODELS, index=0)
            azure_api_base, azure_api_version = "", ""
        else:
            azure_api_base = st.text_input(
                "Azure API Base",
                placeholder="https://<resource>.openai.azure.com",
                value=settings.AZURE_OPENAI_API_BASE,
            )
            azure_api_version = st.text_input("Azure API Version", value=settings.AZURE_OPENAI_API_VERSION)
            api_key = st.text_input("Azure API Key", type="password", value=settings.AZURE_OPENAI_API_KEY, help="Hoặc AZURE_OPENAI_API_KEY.")
            model = st.text_input(
                "Deployment name (Azure)",
                placeholder="vd: gpt-4o-mini-deploy",
                value=settings.AZURE_OPENAI_DEPLOYMENT,
            )
        with st.expander("ℹ️ Notes"):
            st.markdown("- App **không lưu** API key hay source code; mọi thứ ở trong **phiên làm việc hiện tại**.")

# ============== Khởi tạo LLM client & Chat ==============
if provider == "Azure OpenAI":
    client = AzureOpenAIChatClient(
        api_key=api_key or settings.AZURE_OPENAI_API_KEY,
        api_base=azure_api_base or settings.AZURE_OPENAI_API_BASE,
        api_version=azure_api_version or settings.AZURE_OPENAI_API_VERSION,
    )
else:
    client = OpenAIChatClient(api_key=api_key or settings.OPENAI_API_KEY)

# ============== Khởi tạo Store & ChatBot ==============
store = SessionStateStore()
chatbot = ChatConversation(client=client, state_store=store)
state: SessionState = store.get()

# set model in state
state.model = model  
store.set(state)

# ============== Panel (code) ==============
# ---------- Container khung input + diff ----------
with st.container(border=True):
    # Input code (gốc)
    code_text = st.text_area(
        "Your code",
        height=280,
        placeholder="Paste your code…",
        label_visibility="visible",
        value=state.origin_code or ""
    )

    # Cập nhật state khi user nhập
    if code_text != (state.origin_code or ""):
        state.fixed_code = ""           # reset khi đổi code gốc
        state.chat_messages = []        # reset chat theo logic bạn đang dùng
        state.origin_code = code_text
        store.set(state)

    # Auto detect ngôn ngữ (không có options UI)
    stripped = (state.origin_code or "").strip()
    if stripped:
        detected_lang = guess_lang_from_code(stripped)
        if detected_lang and detected_lang != state.language:
            state.language = detected_lang
            store.set(state)
        if detected_lang:
            st.success(f"🔍 Đã phát hiện ngôn ngữ: **{detected_lang}**")
        else:
            st.warning("⚠️ Không nhận diện được ngôn ngữ — dùng mặc định 'text'.")

    # Nút Replace / Clear (giữ nguyên)
    col_rp, col_cl = st.columns([1,1])
    with col_rp:
        can_replace = bool((state.fixed_code or "").strip())
        if st.button("↔️ Replace original with fixed", use_container_width=True, disabled=not can_replace):
            state.origin_code = state.fixed_code
            state.fixed_code = ""
            store.set(state)
            st.success("Đã replace: original = fixed")
            st.rerun()

    with col_cl:
        if st.button("🧹 Clear", use_container_width=True):
            state.origin_code = ""
            state.fixed_code = ""
            state.chat_messages = []
            store.set(state)
            st.rerun()

    # Diff và preview fixed — hiển thị ngay trong cùng khung
    if (state.origin_code or "").strip() and (state.fixed_code or "").strip():
        st.markdown("—")
        st.markdown('<div class="section-title">Fixed code</div>', unsafe_allow_html=True)
        st.code(state.fixed_code, language=state.language or "text")

        with st.expander("ℹ️ Diff"):
            filename = "snippet" + EXT_MAP.get(state.language or "text", ".txt")
            diff_html = make_github_like_unified_html(
                state.origin_code,
                state.fixed_code,
                filename_a=filename,
                filename_b=f"{Path(filename).stem}.fixed{Path(filename).suffix}",
                n=3
            )
            st.components.v1.html(
                f'{diff_html}',
                height=380,
                scrolling=True
            )
    else:
        st.caption("Code đã fix sẽ hiển thị ở đây !")


# ============== Chat (Sidebar) ==============
with chat_tab:
    if not (state.origin_code or "").strip():
        st.warning("Hãy nhập code script mới có thể trò chuyện.", icon="⚠️")
    prompt = st.chat_input("Nhập câu hỏi / yêu cầu review / fix…", disabled=not (state.origin_code or "").strip())

    chat_container = st.container(height=420, border=True)
    with chat_container:
        # render history
        for msg in state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if prompt:
            # user message
            with st.chat_message("user"):
                st.markdown(prompt)
                logger.info(f"User prompt: {prompt}")

            # Gọi chatbot
            with st.chat_message("assistant"):
                with st.spinner("Đang soạn câu trả lời…"):
                    reply, new_state, used_tool = chatbot.reply(question=prompt)
                st.markdown(reply)
                logger.info(f"Chatbot reply:\n{reply}")

            # Cập nhật message & state
            new_state.chat_messages.append({"role": "user", "content": prompt})
            new_state.chat_messages.append({"role": "assistant", "content": reply})
            store.set(new_state)

            if used_tool:
                st.rerun()
