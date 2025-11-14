import re

def extract_code_block(md: str) -> str:
    """
    Bỏ cặp ``` ngoài cùng trong chuỗi markdown, trả lại toàn bộ nội dung bên trong.
    Giữ nguyên mọi thứ khác (kể cả ``` nằm trong code).
    Nếu không hợp lệ (không có đủ hai dấu ```), trả về chuỗi gốc (strip).
    """
    if not md:
        return ""

    fence = "```"
    start = md.find(fence)
    if start == -1:
        return md.strip()

    end = md.rfind(fence)
    if end == start:
        return md.strip()  # chỉ có 1 dấu, không hợp lệ

    # Lấy nguyên xi phần bên trong hai fence (không lstrip để không mất indent/dòng đầu)
    inner = md[start + len(fence): end]

    # Nếu có xuống dòng đầu tiên, tách dòng_đầu và phần_còn_lại
    first_line, sep, rest = inner.partition("\n")

    # Regex nhận diện "lang line": chỉ gồm chữ/số/._+- (không khoảng trắng), ví dụ: python, ts, c++, yaml
    lang_pattern = re.compile(r'^[A-Za-z0-9_.+\-]+$')

    if sep and lang_pattern.fullmatch(first_line.strip()):
        # Có dòng ngôn ngữ -> trả lại phần còn lại sau dòng đó (giữ nguyên nội dung)
        return rest
    else:
        # Không có dòng ngôn ngữ -> trả lại toàn bộ inner
        return inner
