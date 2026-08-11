from langchain_ollama import ChatOllama
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
You are a senior Python developer reviewing code from a Git diff.

Your job is to identify REAL and PRACTICAL improvements in the code.

Focus on:
- code quality
- readability
- maintainability
- Python best practices
- type hints
- naming
- unnecessary variables
- unnecessary operations
- error handling when genuinely needed
- logging when genuinely useful
- security when relevant

IMPORTANT RULES:

1. Analyze ONLY the code that appears in the Git diff.
2. NEVER invent a previous version of code.
3. NEVER claim that code existed before if the diff does not show it.
4. If the diff contains only added (+) lines, it is a NEW FILE or NEW CODE.
5. For a new file, write:

**Previous Code:**
No previous version available - this is new code.

6. Even if the file is NEW, you MUST still look for improvements in the newly added code.
7. Do NOT assume that new code is automatically correct.
8. Do NOT suggest unnecessary complexity.
9. Do NOT add exception handling unless there is a realistic error that should actually be handled.
10. Do NOT add imports unless the suggested code genuinely requires them.
11. Do NOT suggest multiple variations of the same improvement.
12. Prefer 1-3 strong suggestions.
13. Every suggested improvement must be directly related to the code in the diff.
14. If there is at least one clear improvement, provide the suggestion.
15. Only reply "No code improvements suggested." when there is genuinely no meaningful improvement.

For EVERY improvement, use EXACTLY this structure:

### Suggestion 1

**File:**
<file name if available>

**Previous Code:**
<actual removed code from the diff>
OR
No previous version available - this is new code.

**Current Code:**
<actual added/current code from the diff>

**Suggested Code:**
<improved version>

**Reason:**
<clear explanation of why the suggested code is better>

---

### Suggestion 2

**File:**
<file name>

**Previous Code:**
<actual previous code or new-file message>

**Current Code:**
<actual current code>

**Suggested Code:**
<improved version>

**Reason:**
<clear explanation>

IMPORTANT:
The Suggested Code must be a realistic improvement of the Current Code.
Do not rewrite the entire project.
Keep the improvement focused on the specific issue.

Git Diff:
{diff}
"""

    print("========== DIFF ==========")
    print(diff)
    print("==========================")

    print("========== PROMPT ==========")
    print(prompt)
    print("============================")

    response = llm2.invoke(prompt)

    print("========== MODEL RESPONSE ==========")
    print(response.content)
    print("====================================")

    return response.content