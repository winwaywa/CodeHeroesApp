import os
from typing import Optional, Tuple
import streamlit as st
from openai import OpenAI, AzureOpenAI

APP_TITLE = "🔎 Code Review & Auto-Fix (Streamlit + OpenAI)"

# ---------- Helpers ----------
def get_client(
    provider: str,
    openai_key: str = "",
    azure_key: str = "",
    azure_api_base: str = "",
    azure_api_version: str = "",
):
    """
    provider: "OpenAI" | "Azure OpenAI"
    - OpenAI: chỉ cần api_key
    - Azure OpenAI: cần api_key + api_base (https://<resource>.openai.azure.com) + api_version (vd: 2024-02-15-preview)
    """
    if provider == "OpenAI":
        key = openai_key or os.getenv("OPENAI_API_KEY", "")
        if not key:
            raise RuntimeError("Chưa nhập OpenAI API Key.")
        # Không nên set env toàn cục trong webapp; truyền trực tiếp cho client an toàn hơn
        return OpenAI(api_key=key)

    # Azure OpenAI
    a_key = azure_key or os.getenv("AZURE_OPENAI_API_KEY", "")
    a_base = azure_api_base or os.getenv("AZURE_OPENAI_API_BASE", "")
    a_ver  = azure_api_version or os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

    if not a_key:
        raise RuntimeError("Chưa nhập Azure OpenAI API Key.")
    if not a_base:
        raise RuntimeError("Chưa nhập Azure OpenAI API Base (ví dụ: https://myres.openai.azure.com).")
    if not a_ver:
        raise RuntimeError("Chưa nhập Azure OpenAI API Version (ví dụ: 2024-02-15-preview).")

    # LƯU Ý: Với Azure, 'model' sẽ là tên DEPLOYMENT, không phải model gốc.
    # Cấu hình base_url tới /openai và gắn api-version qua default_query.
    return AzureOpenAI(
        api_key=a_key,
        azure_endpoint=a_base,
        api_version=a_ver
    )

def safe_decode(file_bytes: bytes) -> str:
    # Thử UTF-8 → UTF-16 → Latin-1 cho các file lạ encoding
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            return file_bytes.decode(enc)
        except Exception:
            continue
    # Nếu vẫn lỗi, đọc "best effort"
    return file_bytes.decode("utf-8", errors="replace")

def guess_lang_from_name(filename: str) -> str:
    ext = (filename or "").lower()
    for k, v in {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".jsx": "jsx",
        ".java": "java",
        ".cs": "csharp",
        ".cpp": "cpp",
        ".cxx": "cpp",
        ".cc": "cpp",
        ".c": "c",
        ".go": "go",
        ".rs": "rust",
        ".rb": "ruby",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".m": "objectivec",
        ".mm": "objectivec",
        ".sh": "bash",
        ".sql": "sql",
        ".html": "html",
        ".css": "css",
        ".json": "json",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".toml": "toml",
        ".md": "markdown",
    }.items():
        if ext.endswith(k):
            return v
    return "text"

def build_review_system_prompt(language: str) -> str:
    return f"""You are a senior {language} code reviewer.
Return a concise, actionable review in Markdown with these sections:

1) Summary — 2-5 bullets describing what this code does.
2) Major Issues — security, correctness, race conditions, resource leaks, undefined behavior.
3) Minor Issues — style, naming, dead code, logging, comments.
4) Performance — hotspots and complexity; be concrete.
5) Security — input validation, injection, secrets, permissions.
6) Tests — propose unit/integration test cases.
7) Fix Plan — a short, ordered plan to fix the most important issues.

If you reference code, quote exact snippets with line numbers if obvious. Keep it practical.
"""

def build_fix_system_prompt(language: str) -> str:
    return f"""You are a senior {language} engineer. Produce a FIXED version of the input code.
Rules:
- Return ONLY the full corrected code block, fenced as ```{language}``` … ``` with no extra commentary.
- Apply the highest-impact fixes from the review (correctness, security, performance, readability).
- Preserve public APIs unless they are clearly wrong; add comments where decisions are non-obvious.
"""

def call_openai_review(client, model: str, language: str, code: str, extra_note: str = "") -> str:
    system_prompt = build_review_system_prompt(language)
    user_prompt = f"""Review the following {language} code and write your feedback in **Vietnamese**.
        ```{language}
        {code}
        Additional context or constraints (optional):
        {extra_note or "(none)"}"""
    
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        )
    return resp.choices[0].message.content


def call_openai_fix(client, model: str, language: str, code: str, review_summary: str = "") -> str:
    system_prompt = build_fix_system_prompt(language)
    user_prompt = f"""Here is the original {language} code and the previous review summary.
        Please produce the FIXED full code only.

        [REVIEW]
        {review_summary or "(no review provided)"}

        [CODE]
        {code}
        ```"""
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
    )
    return resp.choices[0].message.content

def extract_code_block(markdown_text: str) -> Tuple[str, Optional[str]]:
    """
    Tách code block đầu tiên từ Markdown trả về: (code, lang_guess)
    Nếu không có code fence, trả về (toàn bộ text, None)
    """
    if not markdown_text:
        return "", None
    start = markdown_text.find("```")
    if start == -1:
        return markdown_text.strip(), None
    # find closing fence
    first_line_end = markdown_text.find("\n", start + 3)
    fence_lang = markdown_text[start + 3:first_line_end].strip() if first_line_end != -1 else ""
    end = markdown_text.find("```", first_line_end + 1 if first_line_end != -1 else start + 3)
    if end == -1:
        return markdown_text.strip(), None
    code = markdown_text[first_line_end + 1:end] if first_line_end != -1 else ""
    return code.strip(), (fence_lang or None)

# ---------- UI ----------
st.set_page_config(page_title="Code Review & Fix", page_icon="🛠️", layout="wide")
st.title(APP_TITLE)
st.caption(
    "Nhập code ở ô bên dưới **hoặc** upload file. "
    "Bấm **Review** để nhờ OpenAI phân tích, sau đó **Fix code** để tạo bản đã chỉnh."
)

with st.sidebar:
    st.subheader("⚙️ Settings")

    provider = st.selectbox("Provider", ["OpenAI", "Azure OpenAI"], index=0)

    if provider == "OpenAI":
        api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            help="Hoặc đặt qua biến môi trường OPENAI_API_KEY."
        )
        # Model danh sách sẵn có cho OpenAI
        model = st.selectbox(
            "Model (OpenAI)",
            ["gpt-4o-mini", "gpt-4.1-mini", "o4-mini"],
            index=0,
            help="Chọn model của OpenAI."
        )
    else:
        # Azure OpenAI: nhập thủ công
        azure_api_base = st.text_input(
            "Azure API Base",
            placeholder="https://<resource>.openai.azure.com",
            help="Endpoint của Azure OpenAI, ví dụ: https://myres.openai.azure.com"
        )
        azure_api_version = st.text_input(
            "Azure API Version",
            value="2024-02-15-preview",
            help="Ví dụ: 2024-02-15-preview (phụ thuộc subscription của bạn)"
        )
        azure_api_key = st.text_input(
            "Azure API Key",
            type="password",
            help="Hoặc đặt qua AZURE_OPENAI_API_KEY."
        )
        # Với Azure, 'model' = tên DEPLOYMENT
        model = st.text_input(
            "Deployment name (Azure)",
            placeholder="vd: gpt-4o-mini-deploy",
            help="Tên deployment bạn đã tạo trong Azure OpenAI."
        )

    default_lang = st.selectbox(
        "Ngôn ngữ code mặc định (nếu không đoán được từ filename)",
        ["python","javascript","typescript","java","csharp","cpp","go","rust","php","ruby","swift","kotlin","bash","sql","html","css","json","yaml","text"],
        index=0
    )
    note = st.text_area("Ghi chú/tiêu chí review (tuỳ chọn)", placeholder="Ví dụ: ưu tiên performance, tránh thay đổi public API...")
    st.divider()
    st.caption("💡 Tip: Dùng `@st.cache_data` / `@st.cache_resource` để cache dữ liệu/model nếu app lớn.")


tab_paste, tab_file = st.tabs(["✍️ Paste code", "📁 Upload file"])

with tab_paste:
    code_text = st.text_area("Dán code vào đây", height=280, placeholder="Paste your code…")
    paste_lang = st.selectbox("Ngôn ngữ (nếu dán code)", ["(auto from default)"] + [
        "python","javascript","typescript","java","csharp","cpp","go","rust","php","ruby","swift","kotlin","bash","sql","html","css","json","yaml","text"
    ])

with tab_file:
    file = st.file_uploader("Chọn file mã nguồn", type=None, accept_multiple_files=False)
    file_code = ""
    file_lang = None
    if file is not None:
        file_code = safe_decode(file.read())
        file_lang = guess_lang_from_name(file.name)
        st.caption(f"Đã đọc: **{file.name}** — phát hiện ngôn ngữ: `{file_lang}`")
        st.code(file_code[:1000] + ("\n… (truncated)" if len(file_code) > 1000 else ""), language=file_lang)

# Session state
if "last_code" not in st.session_state:
    st.session_state.last_code = ""
if "last_lang" not in st.session_state:
    st.session_state.last_lang = "text"
if "last_review_md" not in st.session_state:
    st.session_state.last_review_md = ""
if "fixed_code_block" not in st.session_state:
    st.session_state.fixed_code_block = ""

# Determine current input
active_code = ""
active_lang = default_lang

if file is not None and file_code:
    active_code = file_code
    active_lang = file_lang or default_lang
elif code_text.strip():
    active_code = code_text
    active_lang = (None if paste_lang == "(auto from default)" else paste_lang) or default_lang
else:
    active_lang = default_lang

# --- Buttons (chỉ để Review) ---
c1, _, _ = st.columns([1, 1, 2])

with c1:
    do_review = st.button(
        "🔍 Review",
        use_container_width=True,
        disabled=(not active_code),
        key="btn_review"
    )

# --- Actions ---

# Khi bấm REVIEW
# Khi bấm REVIEW
if do_review:
    try:
        if provider == "OpenAI":
            client = get_client(
                provider="OpenAI",
                openai_key=(api_key or os.getenv("OPENAI_API_KEY", "")),
            )
        else:
            client = get_client(
                provider="Azure OpenAI",
                azure_key=(azure_api_key or os.getenv("AZURE_OPENAI_API_KEY", "")),
                azure_api_base=(azure_api_base or os.getenv("AZURE_OPENAI_API_BASE", "")),
                azure_api_version=(azure_api_version or os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")),
            )

        with st.status("Đang gửi code lên model để review…", expanded=True) as status:
            st.write("Provider:", provider)
            st.write("Model / Deployment:", model)
            st.write("Language:", active_lang)
            review_md = call_openai_review(client, model, active_lang, active_code, note)
            status.update(label="✅ Review xong", state="complete")

        st.session_state.last_code = active_code
        st.session_state.last_lang = active_lang
        st.session_state.last_review_md = review_md
        st.session_state.fixed_code_block = ""  # reset bản fix cũ
    except Exception as e:
        st.exception(e)

# Nếu đã có review thì mới hiện review + nút FIX
if st.session_state.last_review_md:
    st.subheader("📋 Kết quả Review")
    st.markdown(st.session_state.last_review_md)

    # Cho phép auto-fix ngay sau review (tuỳ chọn)
    auto_fix = st.checkbox("Tự động tạo bản đã sửa ngay sau khi review", value=False)

    # Nút FIX luôn ở đây để chắc chắn đã có review
    do_fix = auto_fix or st.button("🛠️ Fix code", use_container_width=True)

    if do_fix:
        try:
            if provider == "OpenAI":
                client = get_client(
                    provider="OpenAI",
                    openai_key=(api_key or os.getenv("OPENAI_API_KEY", "")),
                )
            else:
                client = get_client(
                    provider="Azure OpenAI",
                    azure_key=(azure_api_key or os.getenv("AZURE_OPENAI_API_KEY", "")),
                    azure_api_base=(azure_api_base or os.getenv("AZURE_OPENAI_API_BASE", "")),
                    azure_api_version=(azure_api_version or os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")),
                )

            with st.status("Đang yêu cầu model tạo bản code đã sửa…", expanded=True) as status:
                fixed_md = call_openai_fix(
                    client,
                    model,  # OpenAI: model id; Azure: deployment name
                    st.session_state.last_lang,
                    st.session_state.last_code,
                    st.session_state.last_review_md,
                )
                status.update(label="✅ Đã tạo bản sửa", state="complete")

            fixed_code, fenced_lang = extract_code_block(fixed_md)
            st.session_state.fixed_code_block = (fixed_code or fixed_md).strip()
        except Exception as e:
            st.exception(e)

# Hiển thị kết quả FIX (nếu có)
if st.session_state.fixed_code_block:
    st.subheader("✅ Code đã Fix")
    st.code(st.session_state.fixed_code_block, language=st.session_state.last_lang or "text")


    # Gợi ý tên file xuất
    download_name = "fixed_code"
    if file is not None and getattr(file, "name", None):
        base = os.path.splitext(file.name)[0]
        ext = os.path.splitext(file.name)[1]
        download_name = f"{base}.fixed{ext or ''}"
    elif st.session_state.last_lang:
        # map đơn giản sang phần mở rộng
        ext_map = {
            "python": ".py","javascript": ".js","typescript": ".ts","java": ".java",
            "csharp": ".cs","cpp": ".cpp","go": ".go","rust": ".rs","php": ".php",
            "ruby": ".rb","swift": ".swift","kotlin": ".kt","bash": ".sh","sql": ".sql",
            "html": ".html","css": ".css","json": ".json","yaml": ".yml","text": ".txt"
        }
        download_name += ext_map.get(st.session_state.last_lang, ".txt")

    st.download_button(
        "⬇️ Tải code đã fix",
        data=st.session_state.fixed_code_block.encode("utf-8"),
        file_name=download_name,
        mime="text/plain",
        use_container_width=True,
    )

st.divider()
with st.expander("ℹ️ Ghi chú triển khai"):
    st.markdown(
        """
    - App này **không lưu** API key hay source code của bạn; mọi thứ ở trong **phiên làm việc hiện tại**.
    - Bạn có thể thay model trong sidebar; với code dài, nên dùng model mạnh hơn (ví dụ `gpt-4.1`).
    - Nếu cần **rule chặt chẽ** hơn (PSR, PEP8, OWASP, MISRA…), hãy viết vào ô *Ghi chú/tiêu chí review*.
    - Để chạy:
    ```bash
    pip install -U streamlit openai
    export OPENAI_API_KEY=sk-...
    streamlit run app.py
    """
    )