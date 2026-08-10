from typing import TypedDict

class WorkflowState(TypedDict):
    user_request: str
    context:list
    analysis: str
    branch_name: str
    commit_message: str
    mr_title: str
    mr_url: str
    approved: bool

    request_valid: bool
    validation_message: str