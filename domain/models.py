from dataclasses import dataclass
from typing import Optional, Tuple

@dataclass
class FixResult:
    fixed_markdown: str
    code_block: str
    fenced_lang: Optional[str]

# Small language map for download extension
EXT_MAP = {
    "python": ".py","javascript": ".js","typescript": ".ts","java": ".java",
    "csharp": ".cs","cpp": ".cpp","go": ".go","rust": ".rs","php": ".php",
    "ruby": ".rb","swift": ".swift","kotlin": ".kt","bash": ".sh","sql": ".sql",
    "html": ".html","css": ".css","json": ".json","yaml": ".yml","text": ".txt"
}