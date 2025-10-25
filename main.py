import io
import os
import zipfile
import streamlit as st

from config.settings import settings
from db.chroma import CHROMA_COLLECTION, build_embedding_fn, get_collection
from db.utils import index_codebase_in_chroma, build_context_md, retrieve_related_code
from infra.factories.code_review_factory import build_code_review_service
from utils.files import iter_zip_code_files
from utils.language import guess_lang_from_name
from utils.markdown import extract_code_block
from domain.models import EXT_MAP

APP_TITLE = "Code Heroes"

st.set_page_config(page_title=APP_TITLE, page_icon="🛠️", layout="wide")
st.title("🛠️" + APP_TITLE)
st.caption("Dán code hoặc upload .zip (thư mục). Review → Fix hàng loạt.")

# ---------------------------
# Sidebar - Provider settings
# ---------------------------
with st.sidebar:
    st.subheader("⚙️ Settings")
    provider = st.selectbox(label="Provider", options=["OpenAI", "Azure OpenAI"], index=1)

    if provider == "OpenAI":
        api_key = st.text_input("OpenAI API Key", type="password",
                                help="Hoặc đặt OPENAI_API_KEY.",
                                value=settings.OPENAI_API_KEY)
        model = st.selectbox("Model (OpenAI)", ["gpt-4o-mini", "gpt-4.1-mini", "o4-mini"], index=0)
        azure_api_base = azure_api_version = ""
    else:
        azure_api_base = st.text_input("Azure API Base",
                                       placeholder="https://<resource>.openai.azure.com",
                                       value=settings.AZURE_OPENAI_API_BASE)
        azure_api_version = st.text_input("Azure API Version", value=settings.AZURE_OPENAI_API_VERSION)
        api_key = st.text_input("Azure API Key", type="password", help="Hoặc AZURE_OPENAI_API_KEY.")
        model = st.text_input("Deployment name (Azure)",
                              placeholder="vd: gpt-4o-mini-deploy",
                              value=settings.AZURE_OPENAI_DEPLOYMENT)

    default_lang = st.selectbox(
        "Ngôn ngữ mặc định",
        [
            "python", "javascript", "typescript", "java", "csharp", "cpp", "go", "rust",
            "php", "ruby", "swift", "kotlin", "bash", "sql", "html", "css", "json", "yaml", "text"
        ],
        index=0
    )

# ---------------------------
# Tabs
# ---------------------------
_tab_paste, _tab_folder = st.tabs(["✍️ Paste code", "📁 Upload thư mục (.zip)"])

# ------------ Paste Tab ------------
with _tab_paste:
    code_text = st.text_area("Dán code", height=280, placeholder="Paste your code…")
    paste_lang = st.selectbox(
        "Ngôn ngữ (nếu dán)",
        ["(auto from default)", "python", "javascript", "typescript", "java", "csharp", "cpp", "go", "rust",
         "php", "ruby", "swift", "kotlin", "bash", "sql", "html", "css", "json", "yaml", "text"]
    )

# ---------- Folder (.zip) Tab ----------
with _tab_folder:
    zip_file = st.file_uploader("Chọn thư mục bằng cách nén thành .zip", type=["zip"], accept_multiple_files=False)
    batch_inputs = []
    skipped = 0
    if zip_file is not None:
        try:
            for rel_path, content in iter_zip_code_files(zip_file.getvalue()):
                lang = guess_lang_from_name(rel_path)
                batch_inputs.append({"name": rel_path, "lang": lang, "code": content})
            # Thông tin
            st.caption(f"Đã đọc **{len(batch_inputs)}** file code hợp lệ từ .zip (đã tự động bỏ qua thư mục rác & file không phù hợp).")
            for it in batch_inputs[:3]:
                preview = it["code"][:800]
                if len(it["code"]) > 800:
                    preview += "\n… (truncated)"
                st.markdown(f"**{it['name']}**  —  lang: `{it['lang'] or default_lang}`")
                st.code(preview, language=it["lang"] or "text")
        except zipfile.BadZipFile:
            st.error("Tệp tải lên không phải .zip hợp lệ.")

# ---------------------------
# Session state mặc định
# ---------------------------
defaults = {
    "last_code": "",
    "last_lang": "text",
    "last_review_md": "",
    "fixed_code_block": "",
    "last_batch_results": [],  # list[ {name, lang, original_code, review_md} ]
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ---------------------------
# Build service (late binding)
# ---------------------------
if provider == "OpenAI":
    service = build_code_review_service("OpenAI", api_key or settings.OPENAI_API_KEY, model)
else:
    service = build_code_review_service(
        "Azure OpenAI",
        api_key or settings.AZURE_OPENAI_API_KEY,
        model,
        azure_api_base=azure_api_base or settings.AZURE_OPENAI_API_BASE,
        azure_api_version=azure_api_version or settings.AZURE_OPENAI_API_VERSION
    )

# ---------------------------
# PASTE actions (đơn lẻ)
# ---------------------------
active_code = ""
active_lang = default_lang
if code_text.strip():
    active_code = code_text
    active_lang = (None if paste_lang == "(auto from default)" else paste_lang) or default_lang

c1, c2, _ = st.columns([1, 1, 2])
with c1:
    do_review_single = st.button("🔍 Review (đoạn code dán)", use_container_width=True, disabled=(not active_code))

if do_review_single:
    try:
        with st.status("Đang review (single)…", expanded=True) as status:
            st.write("Provider:", provider)
            st.write("Model / Deployment:", model)
            st.write("Language:", active_lang)
            review_md = service.review(language=active_lang, code=active_code)
            status.update(label="✅ Review xong", state="complete")
        st.session_state.last_code = active_code
        st.session_state.last_lang = active_lang
        st.session_state.last_review_md = review_md
        st.session_state.fixed_code_block = ""
    except Exception as e:
        st.exception(e)

if st.session_state.last_review_md:
    st.subheader("📋 Kết quả Review (đoạn code dán)")
    st.markdown(st.session_state.last_review_md)
    do_fix_single = st.button("🛠️ Fix code (đoạn code dán)", use_container_width=True)
    if do_fix_single:
        try:
            with st.status("Đang tạo bản sửa…", expanded=True) as status:
                fixed_md = service.fix(
                    language=st.session_state.last_lang,
                    code=st.session_state.last_code,
                    review_summary=st.session_state.last_review_md
                )
                status.update(label="✅ Đã tạo bản sửa", state="complete")
            fixed_code, fenced_lang = extract_code_block(fixed_md)
            st.session_state.fixed_code_block = (fixed_code or fixed_md).strip()
        except Exception as e:
            st.exception(e)

if st.session_state.fixed_code_block:
    st.subheader("✅ Code đã Fix (đoạn code dán)")
    st.code(st.session_state.fixed_code_block, language=st.session_state.last_lang or "text")
    download_name = "fixed_code" + EXT_MAP.get(st.session_state.last_lang, ".txt")
    st.download_button(
        "⬇️ Tải code đã fix",
        data=st.session_state.fixed_code_block.encode("utf-8"),
        file_name=download_name,
        mime="text/plain",
        use_container_width=True,
    )

# ---------------------------
# FOLDER actions (batch)
# ---------------------------
with c2:
    do_review_batch = st.button(
        "🔍 Review toàn bộ thư mục (.zip)",
        use_container_width=True,
        disabled=(len(batch_inputs) == 0)
    )

if do_review_batch:
    try:
        st.session_state.last_batch_results = []

        # Khởi tạo embedding_fn + collection
        emb_fn = build_embedding_fn()
        collection = get_collection(CHROMA_COLLECTION, emb_fn)

        with st.status("Đang index vào ChromaDB…", expanded=True) as s1:
            index_codebase_in_chroma(collection, batch_inputs)
            s1.update(label="✅ Đã index toàn bộ source vào ChromaDB", state="complete")

        with st.status("Đang review folder…", expanded=True) as status:
            st.write("Tổng số file:", len(batch_inputs))
            for item in batch_inputs:
                # Lấy context liên quan từ vector DB
                related = retrieve_related_code(
                    collection=collection,
                    query_text=item["code"],        # truy vấn bằng chính nội dung file
                    exclude_path=item["name"],
                    k=5
                )
                context_md = build_context_md(related)

                # Thực hiện call review service
                review_md = service.review(
                    language=item["lang"] or default_lang,
                    code=item["code"],
                    extra_note=context_md.strip() # context truy vấn được
                )
                st.session_state.last_batch_results.append({
                    "name": item["name"],
                    "lang": item["lang"] or default_lang,
                    "original_code": item["code"],
                    "review_md": review_md
                })
            status.update(label="✅ Review xong thư mục", state="complete")
    except Exception as e:
        st.exception(e)

def build_fixed_zip(items):
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in items:
            fixed_md = service.fix(
                language=item["lang"],
                code=item["original_code"],
                review_summary=item["review_md"]
            )
            fixed_code, _ = extract_code_block(fixed_md)
            content = (fixed_code or fixed_md).strip().encode("utf-8")

            base, ext = os.path.splitext(item["name"])
            out_name = f"{base}.fixed{ext or EXT_MAP.get('text', '.txt')}"
            # out_name vẫn là relative path -> giữ nguyên cấu trúc thư mục
            zf.writestr(out_name, content)
    mem.seek(0)
    return mem.getvalue()

if st.session_state.get("last_batch_results"):
    st.subheader("📦 Kết quả Review theo thư mục")
    for item in st.session_state.last_batch_results:
        st.markdown(f"### 📄 {item['name']}  \n`lang: {item['lang']}`")
        st.markdown(item["review_md"])
        st.divider()

    if st.button("🛠️ Fix tất cả & tải .zip", use_container_width=True):
        try:
            with st.status("Đang tạo gói .zip kết quả…", expanded=True) as status:
                zip_bytes = build_fixed_zip(st.session_state.last_batch_results)
                status.update(label="✅ Hoàn tất đóng gói", state="complete")
            st.download_button(
                "⬇️ Tải folder đã fix (.zip)",
                data=zip_bytes,
                file_name="fixed_folder.zip",
                mime="application/zip",
                use_container_width=True,
            )
        except Exception as e:
            st.exception(e)

# ---------------------------
# Notes
# ---------------------------
st.divider()
with st.expander("ℹ️ Notes"):
    st.markdown(
        """
        - Upload bằng **.zip** sẽ giữ nguyên cấu trúc **subfolders**. App chỉ xử lý các file text phổ biến (xem danh sách phần mở rộng).
        - Với project lớn, cân nhắc chia nhỏ hoặc lọc bớt; model có thể bị rate-limit.
        - App **không lưu** API key hay source code; mọi thứ ở trong **phiên làm việc hiện tại**.
        - Quy chuẩn (PEP8/OWASP/PSR/MISRA…) hãy ghi rõ tại ô ghi chú.
        """
    )
