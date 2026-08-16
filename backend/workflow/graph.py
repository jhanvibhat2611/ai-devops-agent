from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from workflow.state import WorkflowState

from workflow.nodes import (
    validate_request,
    validation_router,
    retrieve_context,
    analyze_requirement,
    generate_code,
    unit_test_agent,
    unit_test_router,
    human_approval,
    approval_router,
    create_branch,
    commit_generated_code,
    create_merge_request,
)


builder = StateGraph(WorkflowState)


# ============================================================
# NODES
# ============================================================

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
    "generate_code",
    generate_code
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
    "commit_generated_code",
    commit_generated_code
)

builder.add_node(
    "unit_test_agent",
    unit_test_agent
)

builder.add_node(
    "create_merge_request",
    create_merge_request
)


# ============================================================
# ENTRY POINT
# ============================================================

builder.set_entry_point(
    "validate_request"
)


# ============================================================
# VALIDATION
# ============================================================

builder.add_conditional_edges(
    "validate_request",
    validation_router,
    {
        "valid": "retrieve_context",
        "invalid": END
    }
)


# ============================================================
# REQUIREMENT ANALYSIS FLOW
# ============================================================

builder.add_edge(
    "retrieve_context",
    "analyze_requirement"
)

builder.add_edge(
    "analyze_requirement",
    "generate_code"
)


# ============================================================
# CODE GENERATION → UNIT TESTING
# ============================================================

builder.add_edge(
    "generate_code",
    "unit_test_agent"
)


# ============================================================
# UNIT TEST → HUMAN APPROVAL
# ============================================================

builder.add_conditional_edges(
    "unit_test_agent",
    unit_test_router,
    {
        "passed": "human_approval",
        "failed": END
    }
)

# ============================================================
# HUMAN APPROVAL ROUTER
# ============================================================

builder.add_conditional_edges(
    "human_approval",
    approval_router,
    {
        "approved": "create_branch",
        "rejected": END
    }
)


# ============================================================
# GITLAB FLOW
# ============================================================

builder.add_edge(
    "create_branch",
    "commit_generated_code"
)

builder.add_edge(
    "commit_generated_code",
    "create_merge_request"
)

builder.add_edge(
    "create_merge_request",
    END
)


# ============================================================
# CHECKPOINTING
# ============================================================

checkpointer = MemorySaver()

graph = builder.compile(
    checkpointer=checkpointer
)