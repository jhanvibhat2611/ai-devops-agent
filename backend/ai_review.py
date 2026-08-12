from langchain_ollama import ChatOllama
import os
from dotenv import load_dotenv

load_dotenv()

llm2 = ChatOllama(
    model=os.getenv("OLLAMA_AI_MODEL")
)


def review_code(diff: str):

    prompt = f"""
You are a Senior Software Engineer.

Review the following Git diff.

Focus on:
- Bugs
- Code Quality
- Readability
- Performance
- Security
- Best Practices

Return your answer in this format:

Summary:
...

Strengths:
- ...

Suggestions:
- ...

Severity:
Low / Medium / High

Git Diff:
{diff}
"""

    response = llm2.invoke(prompt)

    return response.content


def suggest_code(diff: str):

    prompt = f"""
You are a senior Python developer performing a careful code-improvement review.

Analyze ONLY the code shown in the Git diff.

Your goal is to suggest REAL, SAFE, and PRACTICAL improvements.

============================================================
CRITICAL RULE: PRESERVE FUNCTIONALITY
============================================================

Every suggested code change MUST preserve the original behavior of the code.

DO NOT:

- Remove a return statement if the original function returns a value.
- Remove parameters.
- Remove important calculations.
- Remove function calls that affect behavior.
- Change the output or return value unless the suggestion explicitly improves
  an actual bug.
- Replace working code with code that behaves differently without explaining
  the behavioral change.
- Suggest a change merely because it is stylistically different.
- Invent requirements that are not visible in the diff.

If you are not certain that a change is safe, DO NOT suggest it.

============================================================
ANALYSIS RULES
============================================================

Focus on:

- Actual bugs
- Readability
- Maintainability
- Python best practices
- Type hints
- Variable naming
- Unnecessary operations
- Realistic error handling
- Security issues when genuinely relevant
- Performance issues when genuinely relevant

IMPORTANT:

1. Analyze ONLY the code appearing in the Git diff.
2. NEVER invent a previous version.
3. NEVER assume functionality that is not shown.
4. If the diff contains only added (+) lines, treat it as new code.
5. For new code, use:

**Previous Code:**
No previous version available - this is new code.

6. New code can still have meaningful improvements.
7. Do NOT add unnecessary complexity.
8. Do NOT add exception handling unless there is a realistic reason.
9. Do NOT add imports unless genuinely required.
10. Prefer 1-3 strong suggestions.
11. Do not provide multiple variations of the same suggestion.
12. Suggested code must be syntactically valid Python.
13. Suggested code must be a realistic improvement of the current code.
14. Preserve existing function inputs and outputs unless there is a clear bug.
15. If the function returns a value, the suggested version should also return
    the corresponding value.
16. If there is no meaningful improvement, return:

No code improvements suggested.

============================================================
IMPORTANT EXAMPLE
============================================================

If the current code is:

def process(data):
    x = data["name"]
    print(x)
    return x

DO NOT suggest:

def process(data):
    x = data["name"]
    print(x)

because removing `return x` changes the behavior.

A valid improvement could be:

def process(data):
    name = data.get("name")
    print(name)
    return name

ONLY suggest this if handling a missing "name" key is actually a meaningful
improvement for the code shown.

============================================================
OUTPUT FORMAT
============================================================

Return ONLY valid JSON.

Do NOT return:

- Markdown
- ```json
- Explanations outside the JSON
- Introductory text
- Closing remarks

The response MUST start with {{ and end with }}.

Use exactly this structure:

{{
    "suggestions": [
        {{
            "file": "file name",
            "previous_code": "actual removed code OR new-file message",
            "current_code": "actual current code",
            "suggested_code": "improved code",
            "reason": "why this is a meaningful improvement"
        }}
    ]
}}

If there are no meaningful improvements:

{{
    "suggestions": []
}}

============================================================
GIT DIFF
============================================================

{diff}
"""

    print("========== DIFF ==========")
    print(diff)
    print("==========================")

    response = llm2.invoke(prompt)

    print("========== MODEL RESPONSE ==========")
    print(response.content)
    print("====================================")

    return response.content