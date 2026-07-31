from langgraph.graph import StateGraph, END
from workflow.state import WorkflowState
from workflow.nodes import analyze_requirement, create_branch, create_merge_request, human_approval, approval_router, retrieve_context

builder = StateGraph(WorkflowState)
builder.add_node("analyze_requirement", analyze_requirement)
builder.add_node("create_branch", create_branch)
builder.add_node("create_merge_request",create_merge_request)
builder.add_node("human_approval",human_approval)
builder.add_node("retrieve_context",retrieve_context)

builder.set_entry_point("retrieve_context")
builder.add_edge("retrieve_context","analyze_requirement")
builder.add_edge("analyze_requirement","human_approval")
builder.add_conditional_edges(
    "human_approval",
    approval_router,
    {
        "approved":"create_branch",
        "rejected":END
    }
)
builder.add_edge("create_branch","create_merge_request" )
builder.add_edge("create_merge_request",END)
graph = builder.compile()