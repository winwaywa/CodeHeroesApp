

from typing import Dict

SYSTEM_CHAT = (
    "Bạn là trợ lý review/fix code. Trả lời ngắn gọn, rõ ràng, bằng tiếng Việt.\n"
    "- Khi người dùng yêu cầu giải thích/đánh giá (review) code: trả lời trực tiếp dựa trên ngữ cảnh, KHÔNG dùng tool.\n"
    "- Khi người dùng yêu cầu sửa/refactor/điều chỉnh code: hãy gọi function `run_fix` với tham số fix_instructions.\n"
)

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
    ctx = (
        f"Source gốc người dùng nhập vào:\n```\n{origin_code}\n```\n"
        f"Ngôn ngữ: {language}\n"
    )
    if latest_fixed:
        ctx += f"Phiên bản code đã fix gần nhất:\n```\n{latest_fixed}\n```\n"
    return ctx
