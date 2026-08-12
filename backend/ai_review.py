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


def suggest_code(file_contents: list):

    files_text = ""

    for file in file_contents:
        files_text += (
            f"\n===== FILE: {file.get('file', 'Unknown')} =====\n"
            f"{file.get('content', '')}\n"
            f"===== END FILE =====\n"
        )

    prompt = f"""
You are a senior Python developer reviewing source code from a Merge Request.

Analyze ONLY the actual Python source code provided below.

Your job is to identify REAL, PRACTICAL, and JUSTIFIED improvements.

Focus on:

- code quality
- readability
- maintainability
- Python best practices
- type hints when genuinely useful
- meaningful naming improvements
- unnecessary variables
- unnecessary operations
- duplicated or redundant code
- error handling when genuinely needed
- logging when genuinely useful
- security when relevant

IMPORTANT RULES:

1. The provided content is the CURRENT source code from the Merge Request
   source branch.

2. Treat the provided content as NORMAL SOURCE CODE.
   It is NOT a Git diff.

3. NEVER add Git diff formatting.

Do NOT use:

- "+" prefixes
- "-" prefixes
- "@@" headers
- Git diff syntax

4. Do NOT invent previous code.

5. For a NEW file, use exactly:

"No previous version available - this is new code."

------------------------------------------------------------
CURRENT_CODE RULES
------------------------------------------------------------

6. current_code MUST contain the EXACT relevant code copied from
   the provided source.

7. current_code is used by the application to verify that the file
   has not changed before applying a suggestion.

8. Therefore, current_code MUST NOT be modified in ANY way.

9. When copying current_code:

- Do not remove lines.
- Do not add lines.
- Do not reorder lines.
- Do not remove duplicate lines.
- Do not change indentation.
- Do not change spacing.
- Do not change quotes.
- Do not reformat the code.
- Do not simplify the code.
- Do not correct mistakes.
- Do not improve the code.

10. If the source contains duplicate statements, current_code MUST
    contain those duplicate statements exactly as provided.

11. If the source contains poor formatting, current_code MUST preserve
    that formatting.

12. ONLY suggested_code may contain changes.

------------------------------------------------------------
SUGGESTED_CODE RULES
------------------------------------------------------------

13. suggested_code MUST contain normal Python source code only.

14. suggested_code MUST NOT contain:

- "+" prefixes
- "-" prefixes
- "@@" headers
- Markdown
- Markdown code fences
- explanations
- Git diff formatting

15. suggested_code must contain ONLY the improved version of the
    relevant code section.

16. suggested_code must actually fix the problem described in reason.

17. Do NOT preserve a problem that the suggestion claims to fix.

For example, if the current code contains:

print(name)
print(name)

and the reason says the duplicate print is unnecessary, then
suggested_code MUST NOT contain both print statements.

18. If duplicate or redundant code is the actual problem, remove the
    redundancy when doing so provides a clear practical benefit.

19. Do NOT add error handling merely because something COULD theoretically
    fail.

20. Do NOT add default values for missing dictionary keys unless the
    source code gives a genuine reason that missing keys should be handled.

21. Do NOT add type hints merely to make the code look more professional.

22. Do NOT add complexity that is unrelated to the actual problem.

23. Preserve the intended behavior of the original code unless changing
    the behavior is genuinely necessary to fix the identified issue.

24. Prefer the SMALLEST practical change that meaningfully improves
    the code.

------------------------------------------------------------
SUGGESTION COUNT
------------------------------------------------------------

25. Return ONLY ONE strongest suggestion for each file.

26. NEVER return multiple suggestions for the same file.

27. If several improvements are possible, combine only closely related
    improvements into ONE practical suggestion.

28. Do NOT create a suggestion merely for stylistic preference.

29. Only suggest a change when there is a clear practical benefit.

30. If there is no meaningful improvement for a file, do not create
    a suggestion for that file.

31. If there are no meaningful improvements across all files, return:

{{
    "suggestions": []
}}

------------------------------------------------------------
REASON RULES
------------------------------------------------------------

32. The reason MUST accurately describe what changed in suggested_code.

33. Do NOT claim that type hints were added unless suggested_code actually
    contains type hints.

34. Do NOT claim that error handling was added unless suggested_code
    actually contains error handling.

35. Do NOT claim that duplicate code was removed unless suggested_code
    actually removes the duplicate code.

36. Do NOT claim that readability was improved unless there is an actual
    meaningful readability improvement.

------------------------------------------------------------
NEW FILE RULE
------------------------------------------------------------

37. For a NEW file, previous_code MUST be exactly:

"No previous version available - this is new code."

38. Do NOT invent a previous version for a new file.

------------------------------------------------------------
OUTPUT FORMAT
------------------------------------------------------------

39. Return ONLY valid JSON.

40. Do NOT wrap the JSON in Markdown.

41. Do NOT use ```json.

42. Do NOT include any text before or after the JSON.

43. Use exactly this structure:

{{
    "suggestions": [
        {{
            "file": "filename.py",
            "previous_code": "No previous version available - this is new code.",
            "current_code": "EXACT unchanged source code",
            "suggested_code": "improved Python code only",
            "reason": "accurate explanation of the practical improvement"
        }}
    ]
}}

For an EXISTING file:

- previous_code may contain a previous version ONLY if an actual
  previous version is available.
- Never invent a previous version.

For a NEW file:

- previous_code MUST be:
  "No previous version available - this is new code."

------------------------------------------------------------
FINAL VALIDATION BEFORE RESPONDING
------------------------------------------------------------

Before returning the JSON, verify:

1. current_code is copied exactly from the provided source.
2. current_code contains all original duplicate lines.
3. suggested_code is valid Python.
4. suggested_code contains no Git diff markers.
5. suggested_code actually improves the code.
6. suggested_code actually fixes the problem mentioned in reason.
7. The reason matches the actual changes.
8. There is only ONE suggestion per file.
9. No unnecessary complexity was introduced.
10. The response is valid JSON only.

Source Code:

{files_text}
"""

    print("========== SOURCE CODE SENT TO MODEL ==========")
    print(files_text)
    print("===============================================")

    response = llm2.invoke(prompt)

    print("========== MODEL RESPONSE ==========")
    print(response.content)
    print("====================================")

    return response.content