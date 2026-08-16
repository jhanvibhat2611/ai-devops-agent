from typing import TypedDict


class WorkflowState(TypedDict):
    user_request: str

    request_valid: bool
    validation_message: str

    context: list

    analysis: str

    generated_code: str

    branch_name: str
    commit_message: str
    mr_title: str
    mr_url: str

    approved: bool