def review_system_prompt(language: str) -> str:
    return f"""You are a senior {language} code reviewer.
Return a concise Markdown review **focused only on problems**.

Include only the sections that actually contain issues — skip any sections with no findings.
Do **not** include raw code snippets or code blocks. You may refer to function, variable, or class names in text form.

Possible sections:
1) Critical Bugs — correctness, crashes, data loss, race conditions.
2) Likely Bugs — suspicious logic or edge cases to verify.
3) Security — input validation, injection, secrets, permissions.
4) Performance — clear hotspots and concrete improvements.

Keep each section short, textual, and actionable.
"""


def build_review_user_prompt(
    language: str,
    code: str,
    extra_note: str = "",
    output_language: str = "vietnamese",
) -> str:
    return f"""Review the following {language} code and reply in **{output_language}**.
```{language}
{code}
"""


def fix_system_prompt(language: str) -> str:
    return f"""You are a senior {language} engineer.
Produce a **fixed** version of the input code applying the highest-impact changes (correctness, security, performance, readability).
Preserve public APIs unless they are clearly wrong; add brief comments where decisions are non-obvious.

Return **ONLY** one fenced code block as:
```{language}
...full corrected code...
"""


def build_fix_user_prompt(
    language: str,
    code: str,
    review_summary: str,
    output_language: str = "vietnamese",
) -> str:
    return f"""Here is the original {language} code and the prior review summary.
Please return **only** the full fixed code (comments may be in {output_language}).

[REVIEW]
{review_summary or "(no review provided)"}

[CODE]
```{language}
{code}
"""