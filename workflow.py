from typing import TypedDict
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END
from main import create_gitlab_branch
import json
from workflow.state import WorkflowState
from workflow.nodes import analyze_requirement, create_branch
from workflow.graph import graph



result = graph.invoke(
    {
        "user_request": "Create a login system using JWT."
    }
)

print(result)

