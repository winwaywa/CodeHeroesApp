TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_fix",
            "description": "Sửa/refactor code theo yêu cầu hiện tại của người dùng.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fix_instructions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Các bước sửa cụ thể, mỗi phần tử là 1 chỉ thị ngắn, có thể bao gồm: "
                            "bugfix cụ thể, thêm/thay đổi import, refactor, tối ưu hiệu năng, chuẩn hoá style, thêm type hints,…"
                        ),
                    },
                },
                "required": ["fix_instructions"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_rule",
            "description": "Tìm các rule hoặc best practice liên quan đến code theo ngôn ngữ chỉ định.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Câu hỏi hoặc từ khóa về rule/best-practice."
                    },
                    "language": {
                        "type": "string",
                        "description": "Ngôn ngữ lập trình dùng để lọc rule (ví dụ: python, javascript)."
                    }
                },
                "required": ["query", "language"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_review",
            "description": (
                "Xác định trọng tâm review để đánh giá chất lượng đoạn code hiện tại với vai trò một lead developer. "
                "Danh sách tiêu chí sẽ được dùng làm phạm vi review và làm từ khóa truy vấn vào hệ thống RAG."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "review_focus": {
                        "type": "string",
                        "description": (
                            "Danh sách các tiêu chí review, được viết ở dạng từ khóa ngắn gọn, ngăn cách bởi dấu phẩy.\n"
                            "- Nếu người dùng đưa ra yêu cầu cụ thể (ví dụ: 'review code về mặt hiệu suất'), hãy đặt review_focus "
                            "tương ứng với đúng nội dung đó (ví dụ: 'hiệu suất').\n"
                            "- Nếu người dùng chỉ yêu cầu chung chung (ví dụ: 'review giúp đoạn code này'), hãy tự tổng hợp "
                            "một số tiêu chí mà lead developer thường đánh giá, ví dụ: 'độ dễ đọc, cấu trúc, xử lý lỗi, "
                            "bug tiềm ẩn, hiệu suất, bảo mật, đặt tên, khả năng kiểm thử, khả năng bảo trì, quy ước mã hóa'.\n"
                            "- review_focus sẽ được dùng trực tiếp để giới hạn phạm vi đánh giá và làm cơ sở tìm kiếm rule."
                        ),
                    }
                },
                "required": ["review_focus"]
            },
        },
    }

]