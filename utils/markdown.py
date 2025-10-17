from typing import Optional, Tuple

def extract_code_block(markdown_text: str) -> Tuple[str, Optional[str]]:
    if not markdown_text:
        return "", None
    start = markdown_text.find("```")
    if start == -1:
        return markdown_text.strip(), None
    first_line_end = markdown_text.find("\n", start + 3)
    fence_lang = markdown_text[start + 3:first_line_end].strip() if first_line_end != -1 else ""
    end = markdown_text.find("```", first_line_end + 1 if first_line_end != -1 else start + 3)
    if end == -1:
        return markdown_text.strip(), None
    code = markdown_text[first_line_end + 1:end] if first_line_end != -1 else ""
    return code.strip(), (fence_lang or None)