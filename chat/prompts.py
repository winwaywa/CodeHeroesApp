

from typing import Dict

# ============== Dùng cho chatbot để sửa code theo yêu cầu ==============
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


# ============== Dùng cho chatbot để tóm tắt thay đổi giữa 2 phiên bản code ==============
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


# ============== Dùng cho chatbot để chọn tool ==============
def build_system_context(*, origin_code: str, latest_fixed: str, language: str) -> str:
    system = (
        "Bạn là trợ lý hỗ trợ về code (giải thích, review, sửa lỗi, cải tiến). Trả lời ngắn gọn, rõ ràng, bằng tiếng Việt.\n"
        "\n"
        "- Khi người dùng yêu cầu GIẢI THÍCH code (ví dụ: 'giải thích đoạn code', 'dòng này làm gì?'): trả lời trực tiếp, KHÔNG dùng tool.\n"
        "- Khi người dùng yêu cầu REVIEW / ĐÁNH GIÁ code (ví dụ: 'review giúp đoạn code này', 'đánh giá code này có ổn không', "
        "'xem giúp mình code này đã tối ưu chưa'): hãy gọi function `run_review` với tham số `review_focus` mô tả ngắn gọn trọng tâm cần đánh giá.\n"
        "- Khi người dùng yêu cầu SỬA / REFACTOR / TỐI ƯU code (ví dụ: 'hãy sửa lỗi', 'refactor giúp tôi', 'tối ưu hiệu năng đoạn này'): "
        "hãy gọi function `run_fix` với tham số `fix_instructions`.\n"
        "- Khi người dùng hỏi về QUY TẮC, PRETTY CODE, BEST PRACTICE, CODING CONVENTION, cách đặt tên biến/hàm nhưng mà không đề cập đến REVIEW, Đánh giá code: hãy gọi function `search_rule` "
        "với tham số `query` và `language`.\n"
        "- Tuyệt đối KHÔNG tự ý sửa code nếu người dùng không yêu cầu rõ ràng.\n"
        "- Nếu người dùng hỏi ngoài phạm vi lập trình/code: trả về một câu ngắn rằng bạn chỉ hỗ trợ về code và mời họ đặt câu hỏi khác.\n"
        "\n"
        f"Source gốc người dùng nhập vào:\n```\n{origin_code}\n```\n"
        f"Ngôn ngữ: {language}\n"
    )
    if latest_fixed:
        system += (
            "Phiên bản code đã fix gần nhất:\n"
            f"```\n{latest_fixed}\n```\n"
        )
    return system



# ============== Dùng cho chatbot trả lời câu hỏi dựa trên RULES + QUESTION ==============
def build_rule_answer_prompt(*, question: str, rule_snippets: list[dict]) -> dict:
    bullets = "\n".join(
        f"- {s.get('summary','').strip()} (source: {s.get('source_path','unknown')})"
        for s in (rule_snippets or [])[:4]
    )

    system_prompt = (
        "Bạn là code trợ lý hỏi đáp về code. Trả lời NGẮN GỌN, CHÍNH XÁC dựa trên RULES cung cấp. "
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

# ============== Dùng cho chatbot để REVIEW code ==============
def build_review_prompt(
    *,
    language: str,
    base_code: str,
    question: str,
    review_focus: str,
    rule_snippets: list[dict],
) -> dict:
    """
    Build prompt cho việc REVIEW code (có thể có/không có RULES từ RAG).
    - Chỉ review trong phạm vi các tiêu chí được nêu trong review_focus.
    - Không mở rộng sang các khía cạnh khác.
    """

    # Ghép RULES nếu có
    rules_text = ""
    if rule_snippets:
        parts = []
        for i, s in enumerate(rule_snippets, start=1):
            content = (s.get("content") or "").strip()
            source = (s.get("source") or "").strip()
            parts.append(f"-------------- \n {content}\n (Source path của đoạn trên: {source})")

        rules_text = "\n\n".join(parts)

    # ========== SYSTEM PROMPT: Đưa hết yêu cầu vào đây ==========
    system_prompt = (
        "Bạn là một lead developer giàu kinh nghiệm, chuyên review code cho team.\n"
        "\n"
        "NGUYÊN TẮC BẮT BUỘC KHI REVIEW:\n"
        "• CHỈ được review trong PHẠM VI những tiêu chí xuất hiện trong phần **'Những điểm cần tập trung review'**.\n"
        "• KHÔNG mở rộng sang các khía cạnh khác nếu không nằm trong danh sách tiêu chí.\n"
        "• Ưu tiên sử dụng các RULES (nếu có) được cung cấp trong context để lập luận và đưa ra gợi ý.\n"
        "• Trình bày NGẮN GỌN – RÕ RÀNG – DỄ ĐỌC bằng tiếng Việt.\n"
        "• Trả lời dưới dạng bullet, mỗi bullet bắt đầu bằng ký hiệu 💡 và tiêu chí **được bôi đen**.\n"
        "• Mỗi bullet chỉ gồm MỘT nhận xét tương ứng với MỘT tiêu chí duy nhất.\n"
        "• Nếu áp dụng RULES, hãy nêu ngắn gọn lý do hoặc nguyên tắc liên quan kèm source path (ví dụ python_rule.txt)\n"
        "• Không viết lại toàn bộ code, chỉ đưa ra nhận xét và gợi ý cải thiện.\n"
        "• Cuối phần trả lời, thêm một đoạn nhận xét tổng quan ngắn.\n"
    )

    # ========== USER PROMPT: Bối cảnh + dữ liệu ==========
    if rules_text:
        user_prompt = (
            f"Yêu cầu của người dùng:\n{question}\n\n"
            f"Những điểm cần tập trung review (PHẠM VI DUY NHẤT):\n{review_focus}\n\n"
            "Dưới đây là một số RULES / BEST PRACTICES liên quan (trích từ RAG):\n"
            "----------------------------------------\n"
            f"{rules_text}\n"
            "----------------------------------------\n\n"
            "Đoạn code cần review:\n"
            "```code\n"
            f"{base_code}\n"
            "```\n"
            f"Ngôn ngữ code: {language}\n"
        )
    else:
        user_prompt = (
            f"Yêu cầu của người dùng:\n{question}\n\n"
            f"Những điểm cần tập trung review (PHẠM VI DUY NHẤT):\n{review_focus}\n\n"
            "Không có RULES cụ thể trả về từ RAG. Hãy review dựa trên kinh nghiệm cá nhân, "
            "nhưng vẫn CHỈ trong phạm vi các tiêu chí đã nêu.\n\n"
            "Đoạn code cần review:\n"
            "```code\n"
            f"{base_code}\n"
            "```\n"
            f"Ngôn ngữ code: {language}\n"
        )

    return {"system": system_prompt, "user": user_prompt}
