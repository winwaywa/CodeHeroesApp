import re
from typing import Dict, List, Optional

_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".jsx": "jsx",
    ".java": "java",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".cc": "cpp",
    ".c": "c",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".m": "objectivec",
    ".mm": "objectivec",
    ".sh": "bash",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
    ".json": "json",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".toml": "toml",
    ".md": "markdown",
}

def guess_lang_from_name(filename: str) -> str:
    name = (filename or "").lower()
    for ext, lang in _MAP.items():
        if name.endswith(ext):
            return lang
    return "text"

_LANGUAGE_PATTERNS: Dict[str, List[re.Pattern]] = {
    "python": [
        re.compile(r"\bdef\s+\w+\s*\(", re.MULTILINE),
        re.compile(r"\bimport\s+\w+", re.MULTILINE),
        re.compile(r":\s*\n\s+(?:pass|return|if|for|while|self\.)"),
    ],
    "javascript": [
        re.compile(r"function\s+\w+\s*\(", re.MULTILINE),
        re.compile(r"const\s+\w+\s*=", re.MULTILINE),
        re.compile(r"=>\s*{"),
    ],
    "typescript": [
        re.compile(r"\binterface\s+\w+", re.MULTILINE),
        re.compile(r"\btype\s+\w+\s*=", re.MULTILINE),
        re.compile(r":\s*\w+<\w+>"),
    ],
    "java": [
        re.compile(r"\bpublic\s+class\s+\w+", re.MULTILINE),
        re.compile(r"\bpublic\s+static\s+void\s+main", re.MULTILINE),
        re.compile(r"package\s+[a-z0-9_.]+;", re.MULTILINE),
    ],
    "csharp": [
        re.compile(r"\busing\s+System", re.MULTILINE),
        re.compile(r"\bnamespace\s+\w+", re.MULTILINE),
        re.compile(r"\bpublic\s+(?:class|interface)\s+\w+", re.MULTILINE),
    ],
    "cpp": [
        re.compile(r"#include\s*<", re.MULTILINE),
        re.compile(r"\bstd::\w+", re.MULTILINE),
        re.compile(r"\btemplate\s*<", re.MULTILINE),
    ],
    "go": [
        re.compile(r"\bpackage\s+\w+", re.MULTILINE),
        re.compile(r"\bfunc\s+\w+\s*\(", re.MULTILINE),
        re.compile(r"\bimport\s+\(", re.MULTILINE),
    ],
    "rust": [
        re.compile(r"\bfn\s+\w+\s*\(", re.MULTILINE),
        re.compile(r"\blet\s+mut\s+\w+", re.MULTILINE),
        re.compile(r"::\w+::"),
    ],
    "php": [
        re.compile(r"<\?php"),
    ],
    "ruby": [
        re.compile(r"\bdef\s+\w+", re.MULTILINE),
        re.compile(r"\send\b", re.MULTILINE),
        re.compile(r"\brequire\s+['\"]", re.MULTILINE),
    ],
    "swift": [
        re.compile(r"\bimport\s+Foundation", re.MULTILINE),
        re.compile(r"\bfunc\s+\w+\s*\(", re.MULTILINE),
        re.compile(r"\blet\s+\w+\s*=", re.MULTILINE),
    ],
    "kotlin": [
        re.compile(r"\bfun\s+\w+\s*\(", re.MULTILINE),
        re.compile(r"\bval\s+\w+\s*=", re.MULTILINE),
        re.compile(r"\bimport\s+[a-z0-9_.]+", re.MULTILINE),
    ],
    "bash": [
        re.compile(r"^#!/bin/(?:bash|sh)", re.MULTILINE),
        re.compile(r"\becho\s+"),
        re.compile(r"\bfi\b"),
    ],
    "sql": [
        re.compile(r"\bSELECT\b", re.IGNORECASE),
        re.compile(r"\bFROM\b", re.IGNORECASE),
        re.compile(r"\bWHERE\b", re.IGNORECASE),
    ],
    "html": [
        re.compile(r"<!DOCTYPE\s+html>", re.IGNORECASE),
        re.compile(r"<html", re.IGNORECASE),
        re.compile(r"<body", re.IGNORECASE),
    ],
    "css": [
        re.compile(r"\.[a-zA-Z0-9_-]+\s*{"),
        re.compile(r"\bcolor\s*:", re.IGNORECASE),
        re.compile(r"\bdisplay\s*:", re.IGNORECASE),
    ],
    "json": [
        re.compile(r"^\s*{", re.MULTILINE),
        re.compile(r'"\w+"\s*:\s*', re.MULTILINE),
    ],
    "yaml": [
        re.compile(r"^\s*-\s+\w", re.MULTILINE),
        re.compile(r"^\s*\w+\s*:\s*", re.MULTILINE),
    ],
}

def guess_lang_from_code(code: str) -> Optional[str]:
    if not code or not code.strip():
        return None

    scores = {lang: 0 for lang in _LANGUAGE_PATTERNS}
    for lang, patterns in _LANGUAGE_PATTERNS.items():
        for pattern in patterns:
            if pattern.search(code):
                scores[lang] += 1

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    for lang, score in ordered:
        if score == 0:
            return None
        if lang == "json" and not code.lstrip().startswith(("{", "[")):
            continue
        return lang
    return None
