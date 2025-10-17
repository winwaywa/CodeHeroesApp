def review_system_prompt(language: str) -> str:
    return f"""You are a senior {language} code reviewer.
Return a concise, actionable review in Markdown with these sections:

1) Summary — 2-5 bullets describing what this code does.
2) Major Issues — security, correctness, race conditions, resource leaks, undefined behavior.
3) Minor Issues — style, naming, dead code, logging, comments.
4) Performance — hotspots and complexity; be concrete.
5) Security — input validation, injection, secrets, permissions.
6) Tests — propose unit/integration test cases.
7) Fix Plan — a short, ordered plan to fix the most important issues.

If you reference code, quote exact snippets with line numbers if obvious. Keep it practical.
"""


def build_review_user_prompt(language: str, code: str, extra_note: str, output_language: str = "vi") -> str:
    return f"""Review the following {language} code and write your feedback in **{output_language}**.```{language}{code}
    Additional context or constraints (optional):
    {extra_note or "(none)"}
    """

def fix_system_prompt(language: str) -> str:
    return f"""You are a senior {language} engineer. Produce a FIXED version of the input code.
    Rules:

    Return ONLY the full corrected code block, fenced as {language} … ``` with no extra commentary.

    Apply the highest-impact fixes from the review (correctness, security, performance, readability).

    Preserve public APIs unless they are clearly wrong; add comments where decisions are non-obvious.
    """

def build_fix_user_prompt(language: str, code: str, review_summary: str, output_language: str = "vi") -> str:
    return f"""Here is the original {language} code and the previous review summary.
    Please produce the FIXED full code only (answer can be in {output_language}).

    [REVIEW]
    {review_summary or "(no review provided)"}

    [CODE]
    {code}  
    """
