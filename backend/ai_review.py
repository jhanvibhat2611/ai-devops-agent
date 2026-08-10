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
You are a senior Python developer.

Review the following Git diff.

Find practical improvements related to:
- code quality
- readability
- maintainability
- Python best practices
- logging
- type hints
- naming
- error handling

For every improvement, return:

Suggestion:
Reason:
Improved Code:

If there are no improvements, reply exactly:

No code improvements suggested.

Git Diff:
{diff}
"""
    print("========== DIFF ==========")
    print(diff)
    print("==========================")
    print(prompt)
    response = llm2.invoke(prompt)

    print("========== MODEL RESPONSE ==========")
    print(response.content)
    print("====================================")

    return response.content