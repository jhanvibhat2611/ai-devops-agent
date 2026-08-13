from langchain_ollama import ChatOllama
import os
from dotenv import load_dotenv
import json
import ast

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


def suggest_code(file_contents: list, mr_context: list):

    suggestions = []

    for file in file_contents:

        file_name = file.get(
            "file",
            "Unknown"
        )

        source_code = file.get(
            "content",
            ""
        )

        if not source_code.strip():
            continue

        # ============================================================
        # EXTRACT PYTHON FUNCTIONS
        # ============================================================

        try:

            tree = ast.parse(
                source_code
            )

        except SyntaxError:

            print(
                f"⚠️ Could not parse {file_name} as Python."
            )

            continue

        functions = []

        for node in ast.walk(tree):

            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef
                )
            ):

                current_code = ast.get_source_segment(
                    source_code,
                    node
                )

                if current_code:

                    functions.append({
                        "name": node.name,
                        "code": current_code
                    })

        if not functions:
            continue

        # ============================================================
        # BUILD FUNCTION CONTEXT
        # ============================================================

        functions_text = ""

        for function in functions:

            functions_text += (
                f"\n===== FUNCTION: "
                f"{function['name']} =====\n"
                f"{function['code']}\n"
                f"===== END FUNCTION =====\n"
            )

        # ============================================================
        # BUILD MERGE REQUEST CONTEXT
        # ============================================================

        if mr_context:

            context_text = ""

            for mr in mr_context:

                context_text += f"""
Title: {mr.get("title", "")}
Description: {mr.get("description", "")}
Author: {mr.get("author", "")}
"""

        else:

            context_text = (
                "No related Merge Request context was found."
            )

        # ============================================================
        # AI PROMPT
        # ============================================================

        prompt = f"""
You are a senior Python developer reviewing code from a
Merge Request.

Analyze ONLY the Python functions provided below.

Your task is to identify AT MOST ONE REAL, PRACTICAL,
and JUSTIFIED improvement.

============================================================
WHAT COUNTS AS A REAL IMPROVEMENT
============================================================

Consider:

- duplicated code
- unnecessary variables
- unnecessary operations
- confusing logic
- maintainability problems
- meaningful Python best practices
- genuinely useful error handling
- genuinely useful type hints
- security issues when relevant

Do NOT suggest changes merely because you prefer another style.

Do NOT make changes merely for:

- formatting
- quote style
- personal preference
- changing equivalent mathematical formulas
- adding unnecessary type hints
- adding unnecessary error handling
- adding unnecessary complexity

============================================================
IMPORTANT BEHAVIOR RULE
============================================================

The existing code may already be correct.

Do NOT claim that code is incorrect simply because another
implementation is possible.

If two implementations are functionally equivalent, do NOT
describe one as a bug.

For example:

price - (price * discount)

and:

price * (1 - discount)

are mathematically equivalent for the same inputs.

Do NOT suggest changing between them unless there is another
clear practical benefit.

Do NOT invent requirements.

Preserve the original behavior unless the change provides
a clear practical improvement.

============================================================
MERGE REQUEST CONTEXT
============================================================

The following related Merge Requests were retrieved from
Elasticsearch:

{context_text}

Use this context ONLY when it is relevant.

============================================================
SOURCE FUNCTIONS
============================================================

File: {file_name}

{functions_text}

============================================================
FUNCTION SELECTION
============================================================

Choose AT MOST ONE function.

The function_name MUST exactly match one of the functions
provided above.

If there is no meaningful improvement, return:

{{
    "suggestions": []
}}

============================================================
SUGGESTED CODE
============================================================

suggested_code MUST contain the COMPLETE improved function.

It must include the complete function definition and body.

For example:

def find_user(user):
    if user.get("name") == "admin":
        return True
    else:
        return False

can become:

def find_user(user):
    return user.get("name") == "admin"

Do NOT return only:

return user.get("name") == "admin"

The suggested_code MUST be a complete function.

Do NOT include:

- Git diff markers
- +
- -
- @@
- Markdown
- Markdown code fences
- explanations outside the function

============================================================
REASON
============================================================

The reason must accurately describe the actual change.

Do NOT claim:

- duplicate code was removed unless it was removed
- error handling was added unless it was added
- type hints were added unless they were added
- a bug was fixed unless there was actually a bug
- readability improved unless there is a meaningful improvement

============================================================
CURRENT CODE
============================================================

DO NOT return current_code.

The backend will determine current_code itself.

Only return:

- function_name
- suggested_code
- reason

============================================================
OUTPUT FORMAT
============================================================

Return ONLY a JSON object.

Do NOT return Markdown.

Do NOT return ```json.

Do NOT return any text before or after the JSON.

Return exactly:

{{
    "suggestions": [
        {{
            "function_name": "exact_function_name",
            "suggested_code": "complete improved function",
            "reason": "accurate explanation"
        }}
    ]
}}

OR:

{{
    "suggestions": []
}}

============================================================
FINAL CHECK
============================================================

Before returning the JSON, verify:

1. function_name exists in the provided source.
2. suggested_code is a complete function.
3. suggested_code is valid Python.
4. suggested_code contains no Markdown.
5. suggested_code contains no Git diff markers.
6. The change provides a real practical benefit.
7. The original code was not incorrectly called a bug.
8. The reason accurately describes the change.
9. No unnecessary complexity was introduced.
10. Only ONE suggestion is returned.
11. The response is valid JSON.
"""

        # ============================================================
        # SEND TO QWEN
        # ============================================================

        print(
            "\n========== SOURCE FUNCTIONS SENT TO MODEL =========="
        )

        print(
            functions_text
        )

        print(
            "====================================================="
        )

        response = llm2.invoke(
            prompt
        )

        response_text = (
            response.content.strip()
        )

        print(
            "\n========== MODEL RESPONSE =========="
        )

        print(
            response_text
        )

        print(
            "===================================="
        )

        # ============================================================
        # CLEAN RESPONSE
        # ============================================================

        if response_text.startswith("```"):

            response_text = (
                response_text
                .replace(
                    "```json",
                    "",
                    1
                )
                .replace(
                    "```",
                    "",
                    1
                )
                .strip()
            )

        # ============================================================
        # EXTRACT JSON
        # ============================================================

        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1

        if (
            json_start == -1
            or json_end <= json_start
        ):

            print(
                f"⚠️ No JSON object returned "
                f"for {file_name}"
            )

            continue

        json_text = response_text[
            json_start:json_end
        ]

        # ============================================================
        # PARSE JSON
        #
        # strict=False is intentional.
        #
        # Qwen sometimes returns literal newlines inside
        # suggested_code strings. Standard JSON rejects those
        # newlines, while strict=False allows them.
        # ============================================================

        try:

            parsed = json.loads(
                json_text,
                strict=False
            )

        except json.JSONDecodeError as e:

            print(
                f"⚠️ Invalid JSON returned "
                f"for {file_name}: {e}"
            )

            print(
                "Raw model response:"
            )

            print(
                response_text
            )

            continue

        # ============================================================
        # GET SUGGESTIONS
        # ============================================================

        ai_suggestions = parsed.get(
            "suggestions",
            []
        )

        if not isinstance(
            ai_suggestions,
            list
        ):

            print(
                f"⚠️ Invalid suggestions format "
                f"for {file_name}"
            )

            continue

        if not ai_suggestions:
            continue

        # ============================================================
        # ONLY ONE SUGGESTION PER FILE
        # ============================================================

        suggestion = ai_suggestions[0]

        if not isinstance(
            suggestion,
            dict
        ):
            continue

        function_name = suggestion.get(
            "function_name"
        )

        suggested_code = suggestion.get(
            "suggested_code"
        )

        reason = suggestion.get(
            "reason",
            ""
        )

        if not function_name:

            print(
                f"⚠️ AI did not provide "
                f"a function name for {file_name}"
            )

            continue

        if not suggested_code:

            print(
                f"⚠️ AI did not provide "
                f"suggested code for {file_name}"
            )

            continue

        # ============================================================
        # CLEAN SUGGESTED CODE
        # ============================================================

        suggested_code = (
            suggested_code
            .strip()
        )

        if suggested_code.startswith("```"):

            suggested_code = (
                suggested_code
                .replace(
                    "```python",
                    "",
                    1
                )
                .replace(
                    "```",
                    "",
                    1
                )
                .strip()
            )

        # ============================================================
        # FIND EXACT ORIGINAL FUNCTION
        # ============================================================

        matching_function = None

        for function in functions:

            if (
                function["name"]
                == function_name
            ):

                matching_function = function
                break

        if not matching_function:

            print(
                f"⚠️ AI selected unknown "
                f"function: {function_name}"
            )

            continue

        exact_current_code = (
            matching_function["code"]
        )

        # ============================================================
        # VALIDATE SUGGESTED PYTHON
        # ============================================================

        try:

            suggested_tree = ast.parse(
                suggested_code
            )

        except SyntaxError as e:

            print(
                f"⚠️ AI returned invalid "
                f"Python for {function_name}: {e}"
            )

            continue

        # ============================================================
        # MAKE SURE SUGGESTED CODE CONTAINS
        # THE CORRECT COMPLETE FUNCTION
        # ============================================================

        suggested_functions = []

        for node in ast.walk(
            suggested_tree
        ):

            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef
                )
            ):

                suggested_functions.append(
                    node
                )

        matching_suggested_function = None

        for node in suggested_functions:

            if (
                node.name
                == function_name
            ):

                matching_suggested_function = node
                break

        if not matching_suggested_function:

            print(
                f"⚠️ Suggested code does not "
                f"contain the complete function "
                f"{function_name}"
            )

            continue

        # ============================================================
        # REMOVE ACCIDENTAL EXTRA CODE
        #
        # We only want the selected function.
        # ============================================================

        suggested_function_code = (
            ast.get_source_segment(
                suggested_code,
                matching_suggested_function
            )
        )

        if not suggested_function_code:

            print(
                f"⚠️ Could not extract suggested "
                f"function {function_name}"
            )

            continue

        suggested_function_code = (
            suggested_function_code.strip()
        )

        # ============================================================
        # REJECT UNCHANGED SUGGESTIONS
        # ============================================================

        normalized_current = (
            exact_current_code
            .strip()
        )

        normalized_suggested = (
            suggested_function_code
            .strip()
        )

        if (
            normalized_current
            == normalized_suggested
        ):

            print(
                f"ℹ️ AI returned unchanged code "
                f"for {function_name}. "
                f"Skipping suggestion."
            )

            continue

        # ============================================================
        # FINAL SUGGESTION
        # ============================================================

        suggestions.append({

            "file": file_name,

            "function_name": function_name,

            "previous_code": (
                "No previous version available - "
                "this is new code."
            ),

            "current_code": (
                exact_current_code
            ),

            "suggested_code": (
                suggested_function_code
            ),

            "reason": (
                str(reason).strip()
            )
        })

    # ============================================================
    # FINAL RESPONSE
    # ============================================================

    return json.dumps(
        {
            "suggestions": suggestions
        },
        indent=4
    )