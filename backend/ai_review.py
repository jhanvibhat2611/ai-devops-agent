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

        file_name = file.get("file", "Unknown")
        source_code = file.get("content", "")

        if not source_code.strip():
            continue

        # ------------------------------------------------------------
        # Extract Python functions from the source code
        # ------------------------------------------------------------

        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            print(f"⚠️ Could not parse {file_name} as Python.")
            continue

        functions = []

        for node in ast.walk(tree):

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):

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

        # ------------------------------------------------------------
        # Build function context for the AI
        # ------------------------------------------------------------

        functions_text = ""

        for function in functions:

            functions_text += (
                f"\n===== FUNCTION: {function['name']} =====\n"
                f"{function['code']}\n"
                f"===== END FUNCTION =====\n"
            )

        # ------------------------------------------------------------
        # Build Merge Request context
        # ------------------------------------------------------------

        context_text = ""

        if mr_context:

            for mr in mr_context:

                context_text += f"""
Title: {mr.get("title", "")}
Description: {mr.get("description", "")}
Author: {mr.get("author", "")}
"""

        else:

            context_text = "No related Merge Request context was found."

        # ------------------------------------------------------------
        # AI prompt
        # ------------------------------------------------------------

        prompt = f"""
You are a senior Python developer reviewing code from a Merge Request.

Analyze ONLY the Python functions provided below.

Your job is to identify ONE REAL, PRACTICAL, and JUSTIFIED improvement.

Focus on:

- duplicated code
- unnecessary variables
- unnecessary operations
- readability
- maintainability
- Python best practices
- meaningful error handling
- meaningful type hints
- security issues when relevant

Do NOT make changes merely for style.

Do NOT introduce unnecessary complexity.

Do NOT invent requirements.

Do NOT change behavior unless the change genuinely improves the code.

============================================================
IMPORTANT
============================================================

The source code below is the ACTUAL source code from the
Merge Request.

Each function is provided exactly as it exists in the file.

You must choose AT MOST ONE function to improve.

If there is no meaningful improvement, return:

{{
    "suggestions": []
}}

============================================================
CURRENT CODE RULE
============================================================

The backend will determine the exact current_code itself.

Therefore:

DO NOT return current_code.

DO NOT rewrite or copy the current function into the response.

Only identify the function by its exact function name.

============================================================
SUGGESTED CODE RULE
============================================================

suggested_code MUST contain the COMPLETE improved version of
the selected function.

For example, if the original function is:

def find_user(user):
    if user.get("name") == "admin":
        return True
    else:
        return False

and the improvement is to simplify it, suggested_code must be:

def find_user(user):
    return user.get("name") == "admin"

NOT:

return user.get("name") == "admin"

The suggested_code must remain a complete valid Python function.

Do NOT include:

- Git diff markers
- "+"
- "-"
- "@@"
- Markdown
- Markdown code fences
- explanations inside suggested_code

============================================================
REASON RULE
============================================================

The reason must accurately describe the actual change.

Do not claim that:

- duplicate code was removed unless it was removed
- error handling was added unless it was added
- type hints were added unless they were added
- readability was improved unless there is an actual improvement

============================================================
MERGE REQUEST CONTEXT
============================================================

The following Merge Requests were retrieved from Elasticsearch:

{context_text}

Use this context only when it is relevant.

============================================================
FUNCTIONS TO REVIEW
============================================================

File: {file_name}

{functions_text}

============================================================
OUTPUT FORMAT
============================================================

Return ONLY valid JSON.

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

Do not return anything outside the JSON object.
"""

        print(
            "\n========== SOURCE FUNCTIONS SENT TO MODEL =========="
        )
        print(functions_text)
        print("=====================================================")

        response = llm2.invoke(prompt)

        print("\n========== MODEL RESPONSE ==========")
        print(response.content)
        print("====================================")

        # ------------------------------------------------------------
        # Parse AI response
        # ------------------------------------------------------------

        try:

            response_text = response.content.strip()

            # Remove accidental markdown fences if Ollama adds them
            if response_text.startswith("```"):
                response_text = response_text.replace(
                    "```json",
                    "",
                    1
                ).replace(
                    "```",
                    "",
                    1
                ).strip()

            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1

            if json_start == -1 or json_end == 0:
                continue

            parsed = json.loads(
                response_text[json_start:json_end]
            )

        except json.JSONDecodeError:

            print(
                f"⚠️ Invalid JSON returned for {file_name}"
            )

            continue

        ai_suggestions = parsed.get(
            "suggestions",
            []
        )

        if not ai_suggestions:
            continue

        # ------------------------------------------------------------
        # Only ONE suggestion per file
        # ------------------------------------------------------------

        suggestion = ai_suggestions[0]

        function_name = suggestion.get(
            "function_name"
        )

        suggested_code = suggestion.get(
            "suggested_code"
        )

        reason = suggestion.get(
            "reason"
        )

        if not function_name or not suggested_code:
            continue

        # ------------------------------------------------------------
        # Find the EXACT original function
        # ------------------------------------------------------------

        matching_function = None

        for function in functions:

            if function["name"] == function_name:

                matching_function = function
                break

        if not matching_function:
            print(
                f"⚠️ AI selected unknown function "
                f"{function_name}"
            )
            continue

        exact_current_code = matching_function["code"]

        # ------------------------------------------------------------
        # Validate suggested code
        # ------------------------------------------------------------

        try:
            ast.parse(suggested_code)
        except SyntaxError:

            print(
                f"⚠️ AI returned invalid Python for "
                f"{function_name}"
            )

            continue

        # ------------------------------------------------------------
        # Final suggestion
        # ------------------------------------------------------------

        suggestions.append({
            "file": file_name,
            "previous_code": (
                "No previous version available - this is new code."
            ),
            "current_code": exact_current_code,
            "suggested_code": suggested_code,
            "reason": reason
        })

    # ------------------------------------------------------------
    # Final response
    # ------------------------------------------------------------

    return json.dumps(
        {
            "suggestions": suggestions
        },
        indent=4
    )