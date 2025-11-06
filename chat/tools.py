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
    }
]