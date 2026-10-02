import base64
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import uuid
import pytest
from langgraph.types import Command
from workflow.graph import graph
from workflow import nodes
import elasticsearch_client as retrieval
import main


def test_real_langgraph_test_gate_interrupt_and_rejection(monkeypatch):
    llm = Mock()
    llm.invoke.side_effect = [SimpleNamespace(content=json.dumps({"analysis":"Multiply integer by 3",
        "branch_name":"feature/triple", "commit_message":"Add triple", "mr_title":"Triple"})),
        SimpleNamespace(content="def triple(x): return x * 3"),
        SimpleNamespace(content='{"overall_status":"PASS","summary":"Safe arithmetic","findings":[]}')]
    test_llm = Mock()
    test_llm.invoke.return_value = SimpleNamespace(content="from generated_feature import triple\ndef test_triple(): assert triple(4) == 12")
    monkeypatch.setattr(nodes,"llm1",llm)
    monkeypatch.setattr(nodes,"test_llm",test_llm)
    monkeypatch.setattr(nodes,"search_merge_requests",lambda query, pid: [])
    config = {"configurable":{"thread_id":str(uuid.uuid4())}}
    result = graph.invoke({"username":"alice","gitlab_project_id":11,"gitlab_default_branch":"main",
        "gitlab_clone_url":"https://gitlab.com/owner/repo.git", "thread_id":config["configurable"]["thread_id"],
        "target_file":"generated_feature.py","user_request":"Multiply an integer by 3"},config=config)
    assert result["test_passed"] and result["security_passed"]
    assert result["__interrupt__"][0].value["target_file"] == "generated_feature.py"
    rejected = graph.invoke(Command(resume=False),config=config)
    assert rejected["approved"] is False
    assert not rejected.get("mr_url")


def test_elasticsearch_project_identity_and_filter(monkeypatch):
    fake = Mock()
    fake.search.return_value = {"hits":{"hits":[]}}
    monkeypatch.setattr(retrieval,"es",fake)
    for project in (11,22):
        retrieval.index_merge_request({"project_id":project,"mr_id":1,"title":"same IID"})
        retrieval.search_merge_requests("feature",project)
    assert [c.kwargs["id"] for c in fake.index.call_args_list] == ["11:1","22:1"]
    assert [c.kwargs["query"]["bool"]["filter"][0]["term"]["project_id"] for c in fake.search.call_args_list] == [11,22]
    fake.search.side_effect = RuntimeError("offline")
    assert retrieval.search_merge_requests("feature",11) == []


def test_code_diffs_all_files_and_renames(monkeypatch):
    repo = main.Repository("alice",11,"token",{})
    monkeypatch.setattr(main,"get_merge_request",lambda *a: {"diff_refs":{"base_sha":"base","head_sha":"head"}})
    monkeypatch.setattr(main.client,"pages",lambda *a: [
        {"old_path":"old.py","new_path":"new.py","renamed_file":True,"diff":"rename"},
        {"old_path":"added.py","new_path":"added.py","new_file":True,"diff":"add"},
        {"old_path":"deleted.py","new_path":"deleted.py","deleted_file":True,"diff":"delete"}])
    files = Mock(side_effect=lambda path,ref,pid,token: {"content":base64.b64encode(f"{ref}:{path}".encode()).decode()})
    monkeypatch.setattr(main.client,"file_data",files)
    data = main.code_diffs(1,repo)
    assert len(data["files"]) == 3
    assert data["files"][0]["original_code"] == "base:old.py"
    assert data["files"][0]["modified_code"] == "head:new.py"
    assert data["files"][1]["original_code"] is None
    assert data["files"][2]["modified_code"] is None
    assert all(c.args[2:] == (11,"token") for c in files.call_args_list)


def load_frontend(monkeypatch):
    import sys
    root = Path(__file__).resolve().parents[1] / "frontend"
    monkeypatch.syspath_prepend(str(root))
    spec = importlib.util.spec_from_file_location("frontend_agent_test",root / "views" / "agent.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def walk(control):
    yield control
    for child in getattr(control,"controls",[]) or []:
        yield from walk(child)
    content = getattr(control,"content",None)
    if content is not None and not isinstance(content,str):
        yield from walk(content)


def test_flet_inline_selection_preserves_request(monkeypatch):
    import flet as ft
    module = load_frontend(monkeypatch)
    page = SimpleNamespace(auth_token="token", update=lambda: None)
    calls = []
    class API:
        def __init__(self,page): pass
        def start_chat(self,message,thread):
            calls.append((message,thread))
            if len(calls)==1:
                return {"type":"repository_selection","thread_id":"thread","message":"Choose repository"}
            return {"status":"completed","thread_id":"thread","result":{"analysis":"Done"}}
    monkeypatch.setattr(module,"RepositoryAPI",API)
    monkeypatch.setattr(module,"get_gitlab_projects",lambda token: {"projects":[{"id":11,"name":"Repo","path_with_namespace":"owner/Repo","default_branch":"main","http_url_to_repo":"https://gitlab.com/owner/Repo.git"}]})
    view = module.agent_view(page)
    field = next(c for c in walk(view) if isinstance(c,ft.TextField))
    field.value = "Multiply by 3"
    field.on_submit(None)
    dropdown = next(c for c in walk(view) if isinstance(c,ft.Dropdown))
    dropdown.value = "11"
    # Flet stores the label in content for its button controls.
    select = next(c for c in walk(view) if isinstance(c,ft.ElevatedButton) and c.content == "Use repository and continue")
    select.on_click(None)
    assert calls == [("Multiply by 3",None),("Multiply by 3","thread")]
    assert page.gitlab_project_id == 11
    assert page.gitlab_project_name == "owner/Repo"


def test_frontend_api_binds_separate_pages(monkeypatch):
    module = load_frontend(monkeypatch)
    import api
    transport = Mock(return_value=[])
    monkeypatch.setattr(api,"request",transport)
    for pid,user in ((11,"alice"),(22,"bob")):
        module.RepositoryAPI(SimpleNamespace(gitlab_project_id=pid,auth_token=user)).get_branches()
    assert [(c.kwargs["project_id"],c.kwargs["token"]) for c in transport.call_args_list] == [(11,"alice"),(22,"bob")]


@pytest.mark.parametrize("count", [0, 2])
def test_mr_flet_details_render_every_file(monkeypatch, count):
    import flet as ft
    load_frontend(monkeypatch)
    from views import merge_requests as view_module
    class API:
        def __init__(self, page): pass
        def get_merge_requests(self): return []
        def create_merge_request(self, *args): return {"error":True,"message":"Write rejected"}
        def get_merge_request(self, *args):
            return {"iid":1,"title":"Feature","state":"opened","author":{},"source_branch":"feature","target_branch":"main"}
        def get_merge_request_approval_history(self, *args): return {"approvals":[]}
        def get_mr_changes(self, *args):
            return {"files":[{"new_path":f"file-{i}.py","original_code":f"old-{i}","modified_code":f"new-{i}","diff_git":f"diff-{i}"} for i in range(count)]}
    monkeypatch.setattr(view_module,"RepositoryAPI",API)
    page = SimpleNamespace(update=lambda:None)
    view = view_module.merge_requests_view(page)
    field = next(c for c in walk(view) if isinstance(c,ft.TextField) and c.label == "Merge Request ID")
    field.value = "1"
    button = next(c for c in walk(view) if isinstance(c,ft.ElevatedButton) and c.content == "View MR")
    button.on_click(None)
    texts = [c.value for c in walk(view) if isinstance(c,ft.Text)]
    if count == 0:
        assert "No changed files." in texts
    else:
        for i in range(count):
            assert f"file-{i}.py" in texts
            assert f"old-{i}" in texts
            assert f"new-{i}" in texts
            assert f"diff-{i}" in texts
