

from typing import Dict

def build_fix_prompt(*, language: str, base_code: str, fix_instructions: str) -> Dict[str, str]:
    system = (
        "Bạn là trợ lý chỉnh sửa code. "
        "Hãy trả về CHỈ MỘT code block duy nhất nằm giữa cặp ``` ... ``` chứa phiên bản đã sửa. "
        "KHÔNG viết thêm bất kỳ văn bản, tiêu đề, chú thích, giải thích hoặc kí tự thừa TRƯỚC hoặc SAU code block. "
        "KHÔNG được chèn code block thứ hai. "
        "Nếu không thể sửa (thiếu ngữ cảnh), hãy trả về đúng code hiện tại trong một code block duy nhất."
    )
    user = (
        f"Ngôn ngữ: {language}\n"
        f"Yêu cầu fix :\n{fix_instructions}\n"
        f"Code hiện tại:\n```\n{base_code}\n```"
    )
    return {"system": system, "user": user}



def build_summary_prompt(*, language: str, base_code: str, fixed_code: str) -> Dict[str, str]:
    system = (
        "Bạn là reviewer giàu kinh nghiệm. Hãy so sánh hai phiên bản code và "
        "liệt kê thay đổi một cách ngắn gọn, bằng tiếng Việt, dùng gạch đầu dòng '- '. "
        "KHÔNG chèn code block, KHÔNG dài dòng."
    )
    user = (
        f"Ngôn ngữ: {language}\n"
        f"--- ORIGINAL ---\n```\n{base_code}\n```\n"
        f"--- FIXED ---\n```\n{fixed_code}\n```"
    )
    return {"system": system, "user": user}


def build_system_context(*, origin_code: str, latest_fixed: str, language: str) -> str:
    """
    Trả về system context an toàn, bao gồm source gốc và (nếu có) bản fix gần nhất.
    """
    system = (
        "Bạn là trợ lý hỗ trợ về code (review, giải thích, sửa lỗi, cải tiến). Trả lời ngắn gọn, rõ ràng, bằng tiếng Việt.\n"
        "- Khi người dùng hỏi hoặc yêu cầu review/giải thích code (ví dụ: 'giải thích đoạn code', 'đánh giá code này'): trả lời trực tiếp, KHÔNG dùng tool.\n"
        "- Khi người dùng yêu cầu sửa/refactor/điều chỉnh code (ví dụ: 'hãy sửa lỗi', 'refactor giúp tôi'): hãy gọi function `run_fix` với tham số `fix_instructions`.\n"
        "- Khi người dùng hỏi về quy tắc, chuẩn code, best practice, đặt tên biến/hàm, coding convention: hãy gọi function `search_rule` với tham số `query` và `language`.\n"
        "- Tuyệt đối KHÔNG tự ý sửa code nếu không có yêu cầu rõ ràng từ người dùng.\n"
        "- Nếu người dùng đề cập vấn đề ngoài phạm vi lập trình/code: trả về câu fallback ngắn rằng bạn chỉ hỗ trợ về code, sau đó mời họ đặt câu hỏi liên quan đến code.\n"

        f"Source gốc người dùng nhập vào:\n```\n{origin_code}\n```\n"
        f"Ngôn ngữ: {language}\n"
    )
    if latest_fixed:
        system += f"Phiên bản code đã fix gần nhất:\n```\n{latest_fixed}\n```\n"
    return system

def build_rule_answer_prompt(*, question: str, rule_snippets: list[dict]) -> dict:
    """
    Tạo prompt để LLM trả lời câu hỏi dựa trên RULES + QUESTION (ngữ cảnh).
    """
    bullets = "\n".join(
        f"- {s.get('summary','').strip()} (source: {s.get('source_path','unknown')})"
        for s in (rule_snippets or [])[:4]
    )

    system_prompt = (
        "Bạn là code reviewer/assistant. Trả lời NGẮN GỌN, CHÍNH XÁC dựa trên RULES cung cấp. "
        "Nếu có mâu thuẫn giữa các RULES, hãy nêu rõ và chọn phương án hợp lý. "
        "Luôn kèm citation (source) ở các gợi ý quan trọng. Không bịa thông tin ngoài RULES."
    )

    user_prompt = (
        f"QUESTION (người dùng):\n{question.strip()}\n\n"
        f"RULES (ngữ cảnh RAG):\n{bullets if bullets else '- (không có)'}\n\n"
        "YÊU CẦU:\n- Trả lời trực tiếp vào câu hỏi.\n"
        "- Nêu được lý do/nguyên tắc liên quan từ RULES (kèm source).\n"
        "- Nếu RULES không đủ, nói rõ giới hạn thay vì suy đoán."
    )
    return {"system": system_prompt, "user": user_prompt}
