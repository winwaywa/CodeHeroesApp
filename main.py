import streamlit as st
from config.settings import settings
from infra.factories.code_review_factory import build_code_review_service
from utils.decoding import safe_decode
from utils.language import guess_lang_from_name
from utils.markdown import extract_code_block
from domain.models import EXT_MAP
from dotenv import load_dotenv

import chromadb
from chromadb.utils import embedding_functions
import numpy as np
import io
import soundfile as sf
import requests
import os

APP_TITLE = "Code Heroes"
load_dotenv()

st.set_page_config(page_title=APP_TITLE, page_icon="🛠️", layout="wide")
st.title("🛠️ " + APP_TITLE)
st.caption("Nhập code hoặc upload file. Review → Fix.")

# ---- ElevenLabs API ----
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"

def elevenlabs_tts(text, voice_id=ELEVENLABS_VOICE_ID, api_key=ELEVENLABS_API_KEY, model_id="eleven_multilingual_v2"):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "Accept": "audio/mpeg",
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "text": text,
        "model_id": model_id,
        "output_format": "mp3"
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        return response.content
    else:
        raise Exception(f"ElevenLabs TTS error: {response.status_code} {response.text}")

# ---- ChromaDB Embedding ----
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=settings.OPENAI_API_KEY,
    model_name="text-embedding-ada-002"
)
chroma_client = chromadb.Client(
    chromadb.config.Settings(
        persist_directory="./chromadb_data"
    )
)
collection = chroma_client.get_or_create_collection(
    name="code_review_heroes",
    embedding_function=openai_ef
)

with st.sidebar:
    st.subheader("⚙️ Settings")
    provider = st.selectbox(label="Provider", options=["OpenAI", "Azure OpenAI"], index=1)

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
    "last_review_id": "",
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

# ==== LOGIC TÌM VÀ SINH REVIEW ====
SIMILARITY_THRESHOLD = 0.85

def get_similar_review(code):
    results = collection.query(
        query_texts=[code],
        n_results=1
    )
    if results and results.get("distances") and results["distances"][0]:
        score = 1 - results["distances"][0][0]
        if score >= SIMILARITY_THRESHOLD:
            doc = results["documents"][0][0]
            meta = results["metadatas"][0][0]
            return doc, meta, score
    return None, None, None

c1, _, _ = st.columns([1, 1, 2])
with c1:
    do_review = st.button("🔍 Review", use_container_width=True, disabled=(not active_code))

if do_review:
    try:
        ids = collection.get()["ids"]
    except Exception:
        ids = []
    is_empty = (not ids)

    similar_doc, similar_meta, similarity = (None, None, None)
    if not is_empty:
        similar_doc, similar_meta, similarity = get_similar_review(active_code)

    if similar_doc:
        st.session_state.last_code = active_code
        st.session_state.last_lang = active_lang
        st.session_state.last_review_md = similar_doc
        st.session_state.fixed_code_block = ""
        st.markdown(f":bulb: Đã tìm thấy review tương tự trong ChromaDB (similarity: {similarity:.2f})")
    else:
        try:
            with st.status("Đang review…", expanded=True) as status:
                st.write("Provider:", provider)
                st.write("Model / Deployment:", model)
                st.write("Language:", active_lang)
                review_md = service.review(language=active_lang, code=active_code, extra_note=(note + "\n\nLưu ý: Hãy trả lời kết quả review hoàn toàn bằng tiếng Việt."))
                status.update(label="✅ Review xong", state="complete")
            st.session_state.last_code = active_code
            st.session_state.last_lang = active_lang
            st.session_state.last_review_md = review_md
            st.session_state.fixed_code_block = ""

            doc_id = str(hash(active_code + review_md))
            collection.add(
                ids=[doc_id],
                documents=[review_md],
                metadatas=[{
                    "lang": active_lang,
                    "source_code": active_code,
                    "note": note
                }]
            )
            st.session_state.last_review_id = doc_id

        except Exception as e:
            st.exception(e)

if st.session_state.last_review_md:
    st.subheader("📋 Kết quả Review")
    st.markdown(st.session_state.last_review_md)

    # Nút phát giọng nói qua ElevenLabs
    if st.button("🔊 Nghe kết quả review (ElevenLabs TTS)"):
        try:
            audio_bytes = elevenlabs_tts(st.session_state.last_review_md)
            st.audio(audio_bytes, format='audio/mp3')
        except Exception as e:
            st.error(f"Lỗi ElevenLabs TTS: {e}")

    auto_fix = st.checkbox("Tự động tạo bản đã sửa sau review", value=False)
    do_fix = auto_fix or st.button("🛠️ Fix code", use_container_width=True)

    if do_fix:
        try:
            with st.status("Đang tạo bản sửa…", expanded=True) as status:
                fixed_md = service.fix(language=st.session_state.last_lang,
                                       code=st.session_state.last_code,
                                       review_summary=st.session_state.last_review_md)
                status.update(label="✅ Đã tạo bản sửa", state="complete")
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
        - Sau khi review, kết quả sẽ được embed và lưu vào ChromaDB. Bạn có thể tìm kiếm các review tương tự bằng tiếng Việt hoặc bất kỳ ngôn ngữ nào.
        - Nhấn nút 🔊 để nghe nội dung review bằng giọng nói tiếng Việt (dùng ElevenLabs TTS).
        """
    )