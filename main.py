import streamlit as st

from config.settings import settings
from infra.factories.code_review_factory import build_code_review_service
from utils.language import guess_lang_from_code
from utils.markdown import extract_code_block
from domain.models import EXT_MAP
from transformers import VitsModel, AutoTokenizer
import torch
import soundfile as sf
import sounddevice as sd

APP_TITLE = "Code Heroes"

st.set_page_config(page_title=APP_TITLE, page_icon="🛠️", layout="wide")
st.title("🛠️" + APP_TITLE)
st.caption("Dán code và nhận gợi ý review → fix.")

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

code_text = st.text_area("Dán code", height=280, placeholder="Paste your code…")
language_options = [
    "(Chọn ngôn ngữ)",
    "python", "javascript", "typescript", "java", "csharp", "cpp", "go", "rust",
    "php", "ruby", "swift", "kotlin", "bash", "sql", "html", "css", "json", "yaml", "text"
]
unknown_label = language_options[0]

if "paste_lang_value" not in st.session_state:
    st.session_state.paste_lang_value = unknown_label
    st.session_state.paste_lang_auto = True

detected_lang = guess_lang_from_code(code_text) if code_text.strip() else None
if detected_lang and detected_lang not in language_options:
    detected_lang = None

if st.session_state.get("paste_lang_auto", True):
    st.session_state.paste_lang_value = detected_lang or unknown_label

paste_lang = st.selectbox(
    "Ngôn ngữ (nếu dán)",
    language_options,
    key="paste_lang_value"
)

if detected_lang is None:
    st.session_state.paste_lang_auto = paste_lang == unknown_label
else:
    st.session_state.paste_lang_auto = paste_lang == detected_lang

selected_lang = None if paste_lang == unknown_label else paste_lang

# ---------------------------
# Session state mặc định
# ---------------------------
defaults = {
    "last_code": "",
    "last_lang": "text",
    "last_review_md": "",
    "fixed_code_block": "",
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
active_lang = selected_lang or "text"
if code_text.strip():
    active_code = code_text
    active_lang = selected_lang or "text"

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

    # Nút phát giọng nói qua Hugging Face
    if st.button("🔊 Nghe kết quả review"):
        try:
            model = VitsModel.from_pretrained("facebook/mms-tts-vie")  # loads the TTS model
            tokenizer = AutoTokenizer.from_pretrained("facebook/mms-tts-vie")  # loads text processor

            st.info("🎧 Đang tạo và phát giọng nói... vui lòng chờ vài giây.")

            # Prepare input text
            print("🔹 Tokenizing input text...")
            inputs = tokenizer(st.session_state.last_review_md,
                               return_tensors="pt")  # convert text to model-readable format

            # Run model inference
            print("🔹 Generating speech waveform...")
            with torch.no_grad():  # disable gradient calculation (saves memory)
                outputs = model(**inputs)
                waveform = outputs.waveform  # tensor representing the generated speech

            # Save output audio
            output_path = "output.wav"
            sf.write(output_path, waveform.squeeze().cpu().numpy(), 16000)  # 16kHz sample rate
            data, samplerate = sf.read('output.wav')
            st.info("🎤 Đang phát giọng nói...")
            sd.play(data, samplerate)
            sd.wait()
            st.success("✅ Đã đọc xong...")
        except Exception as e:
            st.error(f"Lỗi TTS: {e}")

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

# ---------------------------
# Notes
# ---------------------------
st.divider()
with st.expander("ℹ️ Notes"):
    st.markdown(
        """
        - App hiện chỉ hỗ trợ dán trực tiếp nội dung code (text).
        - Với đoạn code dài, cân nhắc chia nhỏ để tránh giới hạn token hoặc rate-limit.
        - App **không lưu** API key hay source code; mọi thứ ở trong **phiên làm việc hiện tại**.
        - Quy chuẩn (PEP8/OWASP/PSR/MISRA…) hãy ghi rõ tại ô ghi chú.
        """
    )
