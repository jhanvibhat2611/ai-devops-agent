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
You are a Senior Software Engineer.

Analyze the following Git diff and provide code improvement suggestions.

Focus on:
- Code quality
- Readability
- Performance
- Security
- Best practices

If applicable:
- Explain what should be improved.
- Suggest better code snippets.
- Explain why the suggested change is beneficial.

Git Diff:
{diff}
"""

    response = llm2.invoke(prompt)

    return response.content