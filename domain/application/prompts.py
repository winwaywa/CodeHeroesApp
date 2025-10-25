def review_system_prompt(language: str) -> str:
    return f"""You are a senior {language} code reviewer.
Return a **concise Markdown review** listing only real issues and their fixes — no code quotes, no explanations of correct parts.

Include a section **only if it has findings**:

1. **Critical Bugs** — errors causing crashes, data loss, or incorrect behavior.  
2. **Likely Bugs** — suspicious or risky logic.  
3. **Security** — missing validation, secrets exposure, or unsafe handling.  
4. **Performance** — inefficiencies and clear optimization opportunities.

Keep it short, objective, and focused purely on problems and how to fix them.
"""



def build_review_user_prompt(
    language: str,
    code: str,
    extra_note: str = "",
    output_language: str = "vietnamese",
) -> str:
    base_prompt = [
        f"You are a senior code reviewer. Review the following {language} code carefully.",
        f"Reply in **{output_language}** with structured markdown sections (Critical Bugs, Likely Bugs, Security, Performance, Fix Plan, etc.).",
        "",
        f"```{language}",
        code.strip(),
        "```",
    ]
    if extra_note.strip():
        base_prompt += [
            "",
            "---",
            "### Additional Context / Notes",
            extra_note.strip(),
            "---",
            "Consider this context when reviewing the code above.",
        ]

    return "\n".join(base_prompt)



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