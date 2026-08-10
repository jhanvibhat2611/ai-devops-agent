from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from workflow.state import WorkflowState
from workflow.nodes import (
    validate_request,
    validation_router,
    analyze_requirement,
    create_branch,
    create_merge_request,
    human_approval,
    approval_router,
    retrieve_context
)


builder = StateGraph(WorkflowState)

builder.add_node(
    "validate_request",
    validate_request
)

builder.add_node(
    "retrieve_context",
    retrieve_context
)

builder.add_node(
    "analyze_requirement",
    analyze_requirement
)

builder.add_node(
    "human_approval",
    human_approval
)

builder.add_node(
    "create_branch",
    create_branch
)

builder.add_node(
    "create_merge_request",
    create_merge_request
)


builder.set_entry_point("validate_request")

builder.add_conditional_edges(
    "validate_request",
    validation_router,
    {
        "valid": "retrieve_context",
        "invalid": END
    }
)
builder.add_edge(
    "retrieve_context",
    "analyze_requirement"
)

builder.add_edge(
    "analyze_requirement",
    "human_approval"
)

builder.add_conditional_edges(
    "human_approval",
    approval_router,
    {
        "approved": "create_branch",
        "rejected": END
    }
)

builder.add_edge(
    "create_branch",
    "create_merge_request"
)

builder.add_edge(
    "create_merge_request",
    END
)


checkpointer = MemorySaver()

graph = builder.compile(
    checkpointer=checkpointer
)