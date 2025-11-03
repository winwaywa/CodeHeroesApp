# app/main.py
from typing import Dict, List
import streamlit as st

from chat.llm.azure_client import AzureOpenAIChatClient
from chat.llm.openai_client import OpenAIChatClient
from config.constant import APP_TITLE, EXT_MAP, LANGUAGE_OPTIONS, OPENAI_MODELS, PROVIDER_OPTIONS
from config.settings import settings
from stores.session_state_store import SessionState, SessionStateStore
from utils.language import guess_lang_from_code
from chat.chat_conversasion import ChatConversation

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
            api_key = st.text_input("Azure API Key", type="password", help="Hoặc AZURE_OPENAI_API_KEY.")
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
code_text = st.text_area("Your code", height=280, placeholder="Paste your code…")

# Cập nhật state.code khi nhập
if code_text != state.code:
    state.code = code_text
    store.set(state)

# Detect ngôn ngữ từ code
stripped = (state.code or "").strip()
if stripped:
    detected_lang = guess_lang_from_code(stripped)
    if detected_lang:
        # Tự động nhận diện
        if detected_lang != state.language:
            state.language = detected_lang
            store.set(state)
        st.success(f"Đã tự động phát hiện ngôn ngữ: **{detected_lang}**", icon="🔍")
    else:
        # Không detect được -> yêu cầu chọn
        st.warning("Không nhận diện được ngôn ngữ. Vui lòng chọn:", icon="⚠️")
        selected_lang = st.selectbox(
            "Chọn ngôn ngữ",
            LANGUAGE_OPTIONS
        )
        if selected_lang != state.language:
            state.language = selected_lang
            store.set(state)

# fixed code output
if (state.fixed_code or "").strip():
    st.subheader("✅ Code đã Fix")
    st.code(state.fixed_code, language=state.language or "text")
    download_name = "fixed_code" + EXT_MAP.get(state.language or "text", ".txt")
    st.download_button(
        "⬇️ Tải code đã fix",
        data=state.fixed_code.encode("utf-8"),
        file_name=download_name,
        mime="text/plain",
        use_container_width=True,
    )
else:
    st.caption("Code được fix sẽ hiển thị ở đây")

# ============== Chat (Sidebar) ==============
with chat_tab:
    if not (state.code or "").strip():
        st.info("⚠️ Hãy nhập code script mới có thể trò chuyện.")
    prompt = st.chat_input("Nhập câu hỏi / yêu cầu review / fix…", disabled=not (state.code or "").strip())

    chat_container = st.container(height=420, border=True)
    with chat_container:
        # render history
        for msg in state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if prompt:
            # Thêm user message
            state.chat_messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            # Gọi chatbot
            with st.chat_message("assistant"):
                with st.spinner("Đang soạn câu trả lời…"):
                    reply, new_state, handled_tool = chatbot.reply(
                        question=prompt
                    )
                st.markdown(reply)

            # Cập nhật message & state
            new_state.chat_messages.append({"role": "assistant", "content": reply})
            store.set(new_state)

            if handled_tool:
                st.rerun()
