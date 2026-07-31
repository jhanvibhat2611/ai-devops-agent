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
    You are a Senior Software Engineer reviewing a GitLab Merge Request.

    Analyze ONLY the code changes present in the Git diff.

    Your goal is to propose practical code improvements that a developer can directly accept or reject.

    Rules:

    - Focus only on the modified code.
    - Suggest changes only when they provide a clear improvement.
    - Do NOT give generic advice.
    - Do NOT comment on code that is already good.
    - If no improvements are needed, reply:
      "No code improvements suggested."

    For every suggestion, use this format:

    Suggestion Number:

    File:
    <file name if identifiable>

    Current Code:
    ```language
    existing code

Git Diff:
{diff}
"""

    response = llm2.invoke(prompt)

    return response.content