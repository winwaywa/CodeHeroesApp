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

    # Tìm dấu ``` cuối cùng
    end = md.rfind(fence)
    if end == start:
        return md.strip()  # chỉ có 1 dấu, không hợp lệ

    # Lấy nội dung giữa hai fence, bỏ lang nếu có trên dòng đầu
    inner = md[start + len(fence): end].lstrip()

    # Bỏ dòng lang (nếu có), giữ tất cả nội dung còn lại
    if "\n" in inner:
        _, rest = inner.split("\n", 1)
        return rest.rstrip()
    else:
        return inner.strip()
