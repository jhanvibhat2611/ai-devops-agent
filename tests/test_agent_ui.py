"""Presentation and callback contracts for the Agent view; no live API calls."""
from types import SimpleNamespace
from unittest.mock import Mock

import flet as ft
import pytest

from test_integration_contracts import load_frontend, walk


def setup_view(monkeypatch, responses):
    module = load_frontend(monkeypatch)
    api = Mock()
    api.start_chat.side_effect = responses
    api.get_branches.return_value = [{"name": "existing"}]
    monkeypatch.setattr(module, "RepositoryAPI", lambda page: api)
    page = SimpleNamespace(auth_token="fixture", gitlab_project_name="owner/repository", update=lambda: None)
    return module.agent_view(page), api, page


def button(view, label):
    return next(c for c in walk(view) if isinstance(c, (ft.ElevatedButton, ft.OutlinedButton, ft.TextButton))
                and c.content == label)


def submit(view, message):
    field = next(c for c in walk(view) if isinstance(c, ft.TextField) and c.hint_text == "Ask the AI DevOps Agent...")
    field.value = message
    field.on_submit(None)
    return field


def proposal():
    return {"status": "waiting_for_approval", "thread_id": "thread-1", "workflow_id": "workflow-1",
            "target_file": "generated_feature.py", "analysis": "Multiply the input by three.",
            "generated_code": "def triple(number):\n    return number * 3", "branch_name": "feature/triple",
            "commit_message": "Add triple", "mr_title": "Triple feature"}


@pytest.mark.parametrize("approved,existing", [(True, False), (True, True), (False, False)])
def test_one_approval_card_preserves_decision_contract(monkeypatch, approved, existing):
    view, api, page = setup_view(monkeypatch, [proposal()])
    api.send_chat_decision.return_value = {"status": "completed" if approved else "rejected", "thread_id": "thread-1"}
    field = submit(view, "Multiply by three")
    assert field.disabled and button(view, "New chat").disabled
    texts = [c.value for c in walk(view) if isinstance(c, ft.Text)]
    assert texts.count("Proposed Change") == 1
    for label in ("Requirement analyzed", "Code generated", "Tests passed", "Security checks passed", "Awaiting approval"):
        assert label in texts
    code = next(c for c in walk(view) if isinstance(c, ft.Text) and c.value == proposal()["generated_code"])
    assert code.font_family == "Consolas" and code.no_wrap and code.selectable
    panels = [c for c in walk(view) if isinstance(c, ft.Container) and any(n is code for n in walk(c))]
    assert any(c.height and c.height <= 300 and c.padding for c in panels)
    assert any(isinstance(c, ft.Row) and c.scroll == ft.ScrollMode.AUTO for c in walk(view))
    branch = next(c for c in walk(view) if isinstance(c, ft.TextField) and c.label == "New branch name")
    branch.value = "feature/edited"
    dropdown = next(c for c in walk(view) if isinstance(c, ft.Dropdown))
    dropdown.value = "existing" if existing else None
    button(view, "Approve" if approved else "Reject").on_click(None)
    api.send_chat_decision.assert_called_once_with("thread-1", "workflow-1", approved,
                                                 "existing" if existing else "feature/edited", existing)
    assert not field.disabled
    assert button(view, "Approve").disabled and button(view, "Reject").disabled
    assert "Awaiting approval" not in [c.value for c in walk(view) if isinstance(c, ft.Text)]


def test_approval_error_keeps_retry_and_blocks_new_chat(monkeypatch):
    view, api, page = setup_view(monkeypatch, [proposal()])
    api.send_chat_decision.return_value = {"error": True, "message": "Please retry."}
    field = submit(view, "Build a feature")
    button(view, "Approve").on_click(None)
    assert not button(view, "Approve").disabled
    assert not button(view, "Reject").disabled
    assert field.disabled and button(view, "Change repository").disabled
    assert "Please retry." in [c.value for c in walk(view) if isinstance(c, ft.Text)]


def test_chat_bubbles_composer_greeting_and_thread_reset(monkeypatch):
    view, api, page = setup_view(monkeypatch, [
        {"thread_id": "thread-1", "result": {"validation_message": "Please describe a task."}},
        {"thread_id": "thread-1", "message": "Ready"},
        {"thread_id": "thread-2", "message": "Ready"},
    ])
    submit(view, "hi")
    texts = [c.value for c in walk(view) if isinstance(c, ft.Text)]
    assert "You" in texts and "hi" in texts
    assert not any(t.startswith(("You:", "Validation Message:", "Test Result:")) for t in texts)
    assert "Hi! Tell me what you'd like to build, modify, review, or debug." in texts
    conversation = view.controls[2]
    assert conversation.expand and conversation.scroll == ft.ScrollMode.AUTO
    assert all(isinstance(c, ft.Row) for c in conversation.controls)
    assert not any(isinstance(c, ft.TextField) for c in walk(conversation))
    submit(view, "Next")
    button(view, "New chat").on_click(None)
    submit(view, "Fresh")
    assert [call.args for call in api.start_chat.call_args_list] == [("hi", None), ("Next", "thread-1"), ("Fresh", None)]
    assert page.gitlab_project_name == "owner/repository"
    button(view, "Change repository").on_click(None)
    assert page.gitlab_project_name is None


def test_suggestion_code_panels_preserve_api_calls(monkeypatch):
    suggestion = {"file": "feature.py", "current_code": "x = 1", "suggested_code": "x = 2",
                  "reason": "Correct the value", "proposal_id": "proposal-1"}
    view, api, page = setup_view(monkeypatch, [{"type": "suggestion", "mr_iid": 8, "suggestions": [suggestion]}])
    api.accept_ai_suggestion.return_value = {"status": "accepted"}
    submit(view, "Suggest a fix")
    assert len([c for c in walk(view) if isinstance(c, ft.Text) and c.font_family == "Consolas"]) == 2
    button(view, "Accept suggestion").on_click(None)
    api.accept_ai_suggestion.assert_called_once_with(8, "proposal-1")
