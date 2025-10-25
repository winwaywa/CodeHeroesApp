import io
import os
from pathlib import PurePosixPath
import zipfile

from utils.decoding import safe_decode

# ---------- Folder (.zip) Tab ----------
TEXT_EXTS = {
    ".py", ".js", ".ts", ".java", ".cs", ".cpp", ".cc", ".c", ".go", ".rs",
    ".php", ".rb", ".swift", ".kt", ".bash", ".sh", ".sql",
    ".html", ".css", ".json", ".yaml", ".yml", ".txt", ".md"
}

# Chỉ lấy "code" — bỏ tài liệu thuần văn bản nếu muốn (bạn có thể thêm lại .md, .txt nếu cần)
CODE_EXTS = {
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".java", ".kt",
    ".cs",
    ".cpp", ".cc", ".c", ".h", ".hpp",
    ".go",
    ".rs",
    ".php",
    ".rb",
    ".swift",
    ".sql",
    ".bash", ".sh",
    ".html", ".css", ".scss", ".less",
    ".json", ".yaml", ".yml",
}

# Thư mục cần bỏ qua (case-insensitive)
IGNORED_DIRS = {
    "__macosx", "__pycache__", ".git", ".hg", ".svn",
    ".venv", "venv", "env",
    ".idea", ".vscode",
    "node_modules",
    "dist", "build", ".next", ".turbo", ".cache",
    ".mypy_cache", ".pytest_cache", ".tox",
    "site-packages",
    ".egg-info", "coverage", ".coverage"
}

# File không muốn nhận
IGNORED_FILE_ENDSWITH = (
    ".pyc", ".pyo", ".class", ".o", ".so", ".dll", ".dylib", ".a", ".wasm",
    ".map", ".lock", ".log", ".bin", ".dat",
    ".zip", ".tar", ".gz", ".7z", ".rar",
    ".pdf",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
)
IGNORED_FILE_EXACT = {".ds_store"}

# Bỏ qua file quá lớn (tuỳ chỉnh)
MAX_FILE_BYTES = 256 * 1024

def is_text_like(fname: str) -> bool:
    ext = os.path.splitext(fname)[1].lower()
    return ext in TEXT_EXTS

def _normalize_zip_path(p: str) -> PurePosixPath:
    # Chuẩn hoá đường dẫn trong zip (dùng forward-slash)
    pp = PurePosixPath(p)
    # Loại bỏ dẫn đầu './'
    parts = [seg for seg in pp.parts if seg not in (".", "")]
    return PurePosixPath(*parts)

def should_ignore_path(rel_path: str) -> bool:
    p = _normalize_zip_path(rel_path)
    parts_lower = [seg.lower() for seg in p.parts]

    # Bỏ qua nếu bất kỳ "thư mục" nào nằm trong danh sách IGNORED_DIRS
    # (trừ phần cuối nếu đó là file)
    if any(seg in IGNORED_DIRS for seg in parts_lower[:-1]):
        return True

    name_lower = parts_lower[-1]
    # Tên file cụ thể
    if name_lower in IGNORED_FILE_EXACT:
        return True

    # Định dạng file không nhận
    for suf in IGNORED_FILE_ENDSWITH:
        if name_lower.endswith(suf):
            return True

    return False

def is_code_like(fname: str) -> bool:
    ext = os.path.splitext(fname)[1].lower()
    return ext in CODE_EXTS

def iter_zip_code_files(zip_bytes: bytes):
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for info in zf.infolist():
            # Bỏ entry là thư mục
            if info.is_dir():
                continue

            # Bỏ theo thư mục/đường dẫn rác
            if should_ignore_path(info.filename):
                continue

            # Bỏ file không thuộc code (theo phần mở rộng)
            if not is_code_like(info.filename):
                continue

            # Bỏ file quá lớn
            if info.file_size and info.file_size > MAX_FILE_BYTES:
                continue

            with zf.open(info) as fp:
                raw = fp.read()
                if len(raw) > MAX_FILE_BYTES:
                    continue
                try:
                    content = safe_decode(raw)
                except Exception:
                    # Không decode được => bỏ
                    continue
                yield info.filename, content