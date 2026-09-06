from typing import TypedDict


class WorkflowState(TypedDict):

    # ============================================================
    # USER / REPOSITORY CONTEXT
    # ============================================================

    username: str

    gitlab_project_id: int

    gitlab_default_branch: str

    # ============================================================
    # REQUEST
    # ============================================================

    user_request: str

    request_valid: bool
    validation_message: str

    context: list

    analysis: str

    generated_code: str

    # ============================================================
    # TESTING
    # ============================================================

    test_result: str
    test_passed: bool

    # ============================================================
    # SECURITY
    # ============================================================

    security_report: str
    security_passed: bool

    # ============================================================
    # GIT / MERGE REQUEST
    # ============================================================

    branch_name: str
    use_existing_branch: bool

    commit_message: str
    mr_title: str

    mr_iid: int
    mr_url: str

    approved: bool