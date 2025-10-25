import streamlit as st
from config.settings import settings
from infra.factories.code_review_factory import build_code_review_service
from utils.decoding import safe_decode
from utils.language import guess_lang_from_name
from utils.markdown import extract_code_block
from domain.models import EXT_MAP

APP_TITLE = "Code Heroes"

st.set_page_config(page_title=APP_TITLE, page_icon="🛠️", layout="wide")
st.title("🛠️" + APP_TITLE)
st.caption("Nhập code hoặc upload file. Review → Fix.")

with st.sidebar:
    st.subheader("⚙️ Settings")
    provider = st.selectbox(label="Provider",options=["OpenAI", "Azure OpenAI"],index=1)

    if provider == "OpenAI":
        api_key = st.text_input("OpenAI API Key", type="password", help="Hoặc đặt OPENAI_API_KEY.", value=settings.OPENAI_API_KEY)
        model = st.selectbox("Model (OpenAI)", ["gpt-4o-mini", "gpt-4.1-mini", "o4-mini"], index=0)
        azure_api_base = azure_api_version = ""
    else:
        azure_api_base = st.text_input("Azure API Base", placeholder="https://<resource>.openai.azure.com", value=settings.AZURE_OPENAI_API_BASE)
        azure_api_version = st.text_input("Azure API Version", value=settings.AZURE_OPENAI_API_VERSION)
        api_key = st.text_input("Azure API Key", type="password", help="Hoặc AZURE_OPENAI_API_KEY.")
        model = st.text_input("Deployment name (Azure)", placeholder="vd: gpt-4o-mini-deploy", value=settings.AZURE_OPENAI_DEPLOYMENT)

    default_lang = st.selectbox(
        "Ngôn ngữ mặc định", [
            "python","javascript","typescript","java","csharp","cpp","go","rust","php","ruby","swift","kotlin","bash","sql","html","css","json","yaml","text"
        ], index=0)
    note = st.text_area("Ghi chú review (tuỳ chọn)")

# Tabs
_tab_paste, _tab_file = st.tabs(["✍️ Paste code", "📁 Upload file"])

with _tab_paste:
    code_text = st.text_area("Dán code", height=280, placeholder="Paste your code…")
    paste_lang = st.selectbox("Ngôn ngữ (nếu dán)", ["(auto from default)",
        "python","javascript","typescript","java","csharp","cpp","go","rust","php","ruby","swift","kotlin","bash","sql","html","css","json","yaml","text"
    ])

with _tab_file:
    file = st.file_uploader("Chọn file", type=None, accept_multiple_files=False)
    file_code = ""
    file_lang = None
    if file is not None:
        file_code = safe_decode(file.read())
        file_lang = guess_lang_from_name(file.name)
        st.caption(f"Đã đọc: **{file.name}** — phát hiện ngôn ngữ: `{file_lang}`")
        st.code(file_code[:1000] + ("\n… (truncated)" if len(file_code) > 1000 else ""), language=file_lang)

# Session state
for k, v in {
    "last_code": "",
    "last_lang": "text",
    "last_review_md": "",
    "fixed_code_block": "",
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Determine active input
active_code = ""
active_lang = default_lang

if file is not None and file_code:
    active_code = file_code
    active_lang = file_lang or default_lang
elif code_text.strip():
    active_code = code_text
    active_lang = (None if paste_lang == "(auto from default)" else paste_lang) or default_lang

# Build service (late binding to allow sidebar inputs)
service = None
if provider == "OpenAI":
    service = build_code_review_service("OpenAI", api_key or settings.OPENAI_API_KEY, model)
else:
    service = build_code_review_service("Azure OpenAI", api_key or settings.AZURE_OPENAI_API_KEY, model,
                                        azure_api_base=azure_api_base or settings.AZURE_OPENAI_API_BASE,
                                        azure_api_version=azure_api_version or settings.AZURE_OPENAI_API_VERSION)

# Buttons
c1, _, _ = st.columns([1, 1, 2])
with c1:
    do_review = st.button("🔍 Review", use_container_width=True, disabled=(not active_code))

# Actions
if do_review:
    try:
        with st.status("Đang review…", expanded=True) as status:
            st.write("Provider:", provider)
            st.write("Model / Deployment:", model)
            st.write("Language:", active_lang)
            review_md = service.review(language=active_lang, code=active_code, extra_note=note)
            status.update(label="✅ Review xong", state="complete")
        st.session_state.last_code = active_code
        st.session_state.last_lang = active_lang
        st.session_state.last_review_md = review_md
        st.session_state.fixed_code_block = ""
    except Exception as e:
        st.exception(e)

if st.session_state.last_review_md:
    st.subheader("📋 Kết quả Review")
    st.markdown(st.session_state.last_review_md)
    do_fix = st.button("🛠️ Fix code", use_container_width=True)

    if do_fix:
        try:
            with st.status("Đang tạo bản sửa…", expanded=True) as status:
                fixed_md = service.fix(language=st.session_state.last_lang,
                                       code=st.session_state.last_code,
                                       review_summary=st.session_state.last_review_md)
                status.update(label="✅ Đã tạo bản sửa", state="complete")
            from utils.markdown import extract_code_block
            fixed_code, fenced_lang = extract_code_block(fixed_md)
            st.session_state.fixed_code_block = (fixed_code or fixed_md).strip()
        except Exception as e:
            st.exception(e)

if st.session_state.fixed_code_block:
    st.subheader("✅ Code đã Fix")
    st.code(st.session_state.fixed_code_block, language=st.session_state.last_lang or "text")

    download_name = "fixed_code"
    if file is not None and getattr(file, "name", None):
        import os as _os
        base, ext = _os.path.splitext(file.name)
        download_name = f"{base}.fixed{ext or ''}"
    else:
        download_name += EXT_MAP.get(st.session_state.last_lang, ".txt")

    st.download_button(
        "⬇️ Tải code đã fix",
        data=st.session_state.fixed_code_block.encode("utf-8"),
        file_name=download_name,
        mime="text/plain",
        use_container_width=True,
    )

st.divider()
with st.expander("ℹ️ Notes"):
    st.markdown(
        """
        - App này **không lưu** API key hay source code của bạn; mọi thứ ở trong **phiên làm việc hiện tại**.
        - Có thể thay model trong sidebar; với code dài, nên dùng model mạnh hơn.
        - Quy chuẩn (PEP8/OWASP/PSR/MISRA…) hãy ghi rõ tại ô ghi chú.
        """
)