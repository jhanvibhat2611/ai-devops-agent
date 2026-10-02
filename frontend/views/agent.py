"""Agent conversation with inline repository selection and explicit approvals."""
import json
import flet as ft
from api import RepositoryAPI, get_gitlab_projects


def agent_view(page):
    api = RepositoryAPI(page)
    messages = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=10)
    input_box = ft.TextField(hint_text="Ask the AI DevOps Agent...", expand=True)
    active = ft.Text()
    thread_id = None
    busy = False
    awaiting = False
    pending = ""

    def update_active():
        active.value = "Repository: " + (getattr(page, "gitlab_project_name", None) or "not selected")

    def add(text):
        messages.controls.append(ft.Text(str(text), selectable=True))

    def locked(value):
        nonlocal busy
        busy = value
        input_box.disabled = value or awaiting
        change_button.disabled = value or awaiting
        new_button.disabled = value or awaiting
        send_button.disabled = value or awaiting
        page.update()

    def result_message(result, success):
        add(success if result.get("status") in ("posted", "accepted") else result.get("message", "Operation failed."))
        page.update()

    def repository_picker():
        result = get_gitlab_projects(page.auth_token)
        if result.get("error"):
            add(result["message"])
            messages.controls.append(ft.TextButton("Retry repository lookup", on_click=lambda e: repository_picker()))
            page.update()
            return
        projects = result.get("projects", [])
        if not projects:
            add("No accessible repositories found. Check your GitLab membership and token.")
            page.update()
            return
        dropdown = ft.Dropdown(label="GitLab repository", options=[ft.dropdown.Option(str(p["id"]), p.get("path_with_namespace") or p["name"]) for p in projects])
        def select(e):
            nonlocal pending
            project = next((p for p in projects if str(p["id"]) == dropdown.value), None)
            if project is None:
                add("Choose a repository first.")
                page.update()
                return
            page.gitlab_project_id = project["id"]
            page.gitlab_project_name = project.get("path_with_namespace") or project["name"]
            page.gitlab_default_branch = project.get("default_branch")
            page.gitlab_clone_url = project.get("http_url_to_repo")
            update_active()
            dropdown.disabled = True
            select_button.disabled = True
            locked(True)
            try:
                response = api.start_chat(pending, thread_id)
                if response.get("error"):
                    dropdown.disabled = False
                    select_button.disabled = False
                else:
                    pending = ""
                handle(response)
            finally:
                locked(False)
        select_button = ft.ElevatedButton("Use repository and continue", on_click=select)
        messages.controls.append(ft.Column([dropdown, select_button]))
        page.update()

    def handle(response):
        nonlocal thread_id, awaiting
        if response.get("error"):
            add(response.get("message", "Request failed."))
            page.update()
            return
        thread_id = response.get("thread_id", thread_id)
        project = response.get("repository")
        if project:
            page.gitlab_project_id = project["id"]
            page.gitlab_project_name = project.get("path_with_namespace") or project["name"]
            page.gitlab_default_branch = project.get("default_branch")
            page.gitlab_clone_url = project.get("http_url_to_repo")
            update_active()
        kind = response.get("type")
        if kind == "repository_selection":
            add(response["message"])
            repository_picker()
        elif kind == "mr_selection":
            add(response.get("message", "Select an MR."))
            for mr in response.get("merge_requests", []):
                def select_mr(e, iid=mr["mr_iid"]):
                    locked(True)
                    try:
                        handle(api.start_chat(str(iid), thread_id))
                    finally:
                        locked(False)
                messages.controls.append(ft.TextButton(f"!{mr['mr_iid']} — {mr['title']}", on_click=select_mr))
        elif kind == "review":
            add(response.get("review", "No review returned."))
            def post(e):
                result_message(api.post_ai_review(response["mr_iid"], response["review_id"]), "Review posted to GitLab.")
            messages.controls.append(ft.ElevatedButton("Post this review", on_click=post))
        elif kind == "suggestion":
            for suggestion in response.get("suggestions", []):
                add(f"File: {suggestion['file']}\nCurrent code:\n{suggestion['current_code']}\nSuggested code:\n{suggestion['suggested_code']}\nReason: {suggestion.get('reason', '')}")
                def accept(e, proposal=suggestion["proposal_id"], iid=response["mr_iid"]):
                    result_message(api.accept_ai_suggestion(iid, proposal), "Suggestion committed to the MR source branch.")
                def post(e, suggestion=suggestion, iid=response["mr_iid"]):
                    result_message(api.post_ai_suggestion(iid, json.dumps(suggestion, indent=2)), "Suggestion posted.")
                messages.controls.append(ft.Row([ft.ElevatedButton("Accept suggestion", on_click=accept),
                    ft.TextButton("Post suggestion", on_click=post), ft.TextButton("Reject", on_click=lambda e: result_message({"message": "Suggestion rejected; no changes made."}, ""))]))
            if not response.get("suggestions"):
                add("No applicable suggestions returned.")
        elif response.get("status") == "waiting_for_approval":
            awaiting = True
            add(f"Target file: {response['target_file']}\nAnalysis: {response['analysis']}\nCommit: {response['commit_message']}\nMR: {response['mr_title']}\nProposed code:\n{response.get('generated_code', '')}")
            branch = ft.TextField(label="New branch name", value=response.get("branch_name", ""))
            branches = api.get_branches()
            if isinstance(branches, dict):
                add(branches.get("message", "Unable to load branches."))
                branches = []
            existing = ft.Dropdown(label="Or choose an existing branch", options=[ft.dropdown.Option(b["name"]) for b in branches])
            proposal_thread = thread_id
            def decision(e, approved):
                nonlocal awaiting
                approve_button.disabled = reject_button.disabled = True
                locked(True)
                result = api.send_chat_decision(proposal_thread, response["workflow_id"], approved, existing.value or branch.value, bool(existing.value))
                if result.get("error"):
                    add(result.get("message", "Decision failed. Inspect backend status before retrying."))
                    approve_button.disabled = reject_button.disabled = False
                else:
                    awaiting = False
                    handle(result)
                locked(False)
            approve_button = ft.ElevatedButton("Approve", on_click=lambda e: decision(e, True))
            reject_button = ft.OutlinedButton("Reject", on_click=lambda e: decision(e, False))
            messages.controls.append(ft.Column([branch, existing, ft.Row([approve_button, reject_button])]))
        else:
            result = response.get("result", {})
            if response.get("mr_url"):
                add("Merge Request created: " + response["mr_url"])
            elif response.get("status") == "rejected":
                add("Workflow rejected. No branch or MR created.")
            else:
                for key in ("validation_message", "analysis", "test_result", "security_report"):
                    if result.get(key):
                        add(f"{key.replace('_', ' ').title()}: {result[key]}")
                if not result:
                    add(response.get("message", "Request completed."))
        page.update()

    def send(e):
        nonlocal pending
        if busy or awaiting or not (input_box.value or "").strip():
            return
        pending = input_box.value.strip()
        add("You: " + pending)
        input_box.value = ""
        locked(True)
        try:
            handle(api.start_chat(pending, thread_id))
        finally:
            locked(False)

    def reset(e, change=False):
        nonlocal thread_id, pending
        if busy or awaiting:
            return
        thread_id, pending = None, ""
        messages.controls.clear()
        if change:
            for name in ("gitlab_project_id", "gitlab_project_name", "gitlab_default_branch", "gitlab_clone_url"):
                setattr(page, name, None)
            add("Enter a request; choose its repository inline.")
        update_active()
        page.update()

    send_button = ft.ElevatedButton("Send", on_click=send)
    new_button = ft.OutlinedButton("New Chat", on_click=reset)
    change_button = ft.TextButton("Change repository", on_click=lambda e: reset(e, True))
    input_box.on_submit = send
    update_active()
    return ft.Column([ft.Text("AI DevOps Agent", size=28), ft.Row([active, change_button]), messages,
                      ft.Row([input_box, send_button, new_button])], expand=True)
