from typing import Dict


APP_TITLE = "Code Heroes"

EXT_MAP: Dict[str, str] = {
    "python": ".py", "javascript": ".js", "typescript": ".ts", "java": ".java",
    "csharp": ".cs", "cpp": ".cpp", "go": ".go", "rust": ".rs", "php": ".php",
    "ruby": ".rb", "swift": ".swift", "kotlin": ".kt", "bash": ".sh", "sql": ".sql",
    "html": ".html", "css": ".css", "json": ".json", "yaml": ".yml", "text": ".txt",
}

LANGUAGE_OPTIONS = [
    "python", "javascript", "typescript", "java", "csharp", "cpp",
    "go", "rust", "php", "ruby", "swift", "kotlin", "bash", "sql", "html", "css", "json",
    "yaml", "text"
]
OPENAI_MODELS = ["gpt-4o-mini", "gpt-4.1-mini", "o4-mini"]
PROVIDER_OPTIONS = ["OpenAI", "Azure OpenAI"]