"""Agent conversation with inline repository selection and explicit approvals."""
import json
import flet as ft
from api import RepositoryAPI, get_gitlab_projects


def agent_view(page):
    api = RepositoryAPI(page)
    messages = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=16, auto_scroll=True)
    input_box = ft.TextField(hint_text="Ask the AI DevOps Agent...", expand=True)
    active = ft.Text(size=12, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
    working = ft.Row([ft.ProgressRing(width=14, height=14, stroke_width=2),
                      ft.Text("Working on your request...", size=12)], visible=False)

    thread_id = None
    busy = False
    awaiting = False
    pending = ""

    def update_active():
        active.value = getattr(page, "gitlab_project_name", None) or "No repository selected"

    def code_block(code):
        return ft.Container(
            ft.Column([ft.Row([ft.Text(str(code), font_family="Consolas", size=12,
                                      selectable=True, no_wrap=True)], scroll=ft.ScrollMode.AUTO)],
                      scroll=ft.ScrollMode.AUTO),
            height=min(300, max(85, (str(code).count("\n") + 2) * 19)),
            padding=14, border_radius=10, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        )

    def card(controls, user=False):
        body = ft.Column([
            ft.Row([ft.Icon(ft.Icons.PERSON_OUTLINE if user else ft.Icons.AUTO_AWESOME,
                           size=16, color=ft.Colors.PRIMARY),
                    ft.Text("You" if user else "AI DevOps Agent", size=12,
                            weight=ft.FontWeight.W_600)], spacing=7),
            *controls,
        ], spacing=12, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        bubble = ft.Container(body, padding=18, border_radius=16,
                              bgcolor=ft.Colors.SECONDARY_CONTAINER if user else ft.Colors.SURFACE_CONTAINER_LOW,
                              border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT), expand=True)
        messages.controls.append(ft.Row(
            [ft.Container(width=32), bubble] if user else [bubble, ft.Container(width=16)],
            vertical_alignment=ft.CrossAxisAlignment.START,
        ))
        return body

    def add(text, user=False):
        return card([ft.Text(str(text), selectable=True, size=14)], user=user)

    def labeled(label, value):
        return ft.Column([ft.Text(label, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                          ft.Text(str(value), selectable=True, size=14)], spacing=4)

    def workflow_status(result=None, approval=False):
        result = result or {}
        failure = result.get("test_failure")
        stages = [("Requirement analyzed", bool(result.get("analysis"))),
                  ("Code generated", bool(result.get("generated_code"))),
                  ("Tests passed", result.get("test_passed") is True),
                  ("Security checks passed", result.get("security_passed") is True)]
        rows = [ft.Text("Workflow", weight=ft.FontWeight.W_600, size=14)]
        for label, complete in stages:
            if complete or approval:
                rows.append(ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=16, color=ft.Colors.PRIMARY),
                                    ft.Text(label, size=12)], spacing=8))
        if approval or failure or result.get("security_passed") is False:
            rows.append(ft.Row([ft.Icon(ft.Icons.PENDING_OUTLINED if approval else ft.Icons.ERROR_OUTLINE,
                                       size=16, color=ft.Colors.PRIMARY if approval else ft.Colors.ERROR),
                                ft.Text("Awaiting approval" if approval else "Workflow needs attention", size=12)], spacing=8))
        return ft.Container(ft.Column(rows, spacing=7), padding=14, border_radius=10,
                            bgcolor=ft.Colors.SURFACE_CONTAINER)

    def workflow_details(result):
        controls = []
        for key, label in (("analysis", "Requirement analysis"), ("test_result", "Test output"),
                           ("security_report", "Security report")):
            if result.get(key):
                controls.append(labeled(label, result[key]))
        if result.get("generated_code"):
            controls.extend([ft.Text("Generated code", size=12), code_block(result["generated_code"])])
        failure = result.get("test_failure") or {}
        for key, label in (("stage", "Stage"), ("error_category", "Category"),
                           ("error_code", "Error code"), ("safe_message", "Message")):
            if failure.get(key):
                controls.append(labeled(label, failure[key]))
        return ft.ExpansionTile(title=ft.Text("Workflow details", size=13), controls=controls)


    def locked(value):
        nonlocal busy
        busy = value
        working.visible = value
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
            body = add(result["message"])
            body.controls.append(ft.TextButton("Retry repository lookup", on_click=lambda e: repository_picker()))
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
        card([ft.Text("Choose a GitLab repository for this request", weight=ft.FontWeight.W_600), dropdown, select_button])
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
            repository_picker()
        elif kind == "mr_selection":
            selection_card = add(response.get("message", "Select an MR."))
            for mr in response.get("merge_requests", []):
                def select_mr(e, iid=mr["mr_iid"]):
                    locked(True)
                    try:
                        handle(api.start_chat(str(iid), thread_id))
                    finally:
                        locked(False)
                selection_card.controls.append(ft.TextButton(f"!{mr['mr_iid']} — {mr['title']}", on_click=select_mr))
        elif kind == "review":
            review_card = add(response.get("review", "No review returned."))
            def post(e):
                result_message(api.post_ai_review(response["mr_iid"], response["review_id"]), "Review posted to GitLab.")
            review_card.controls.append(ft.ElevatedButton("Post this review", on_click=post))
        elif kind == "suggestion":
            for suggestion in response.get("suggestions", []):
                suggestion_card = card([labeled("File", suggestion["file"]),
                    ft.Text("Current code", size=12), code_block(suggestion["current_code"]),
                    ft.Text("Suggested code", size=12), code_block(suggestion["suggested_code"]),
                    ft.Text(suggestion.get("reason", ""), selectable=True)])
                def accept(e, proposal=suggestion["proposal_id"], iid=response["mr_iid"]):
                    result_message(api.accept_ai_suggestion(iid, proposal), "Suggestion committed to the MR source branch.")
                def post(e, suggestion=suggestion, iid=response["mr_iid"]):
                    result_message(api.post_ai_suggestion(iid, json.dumps(suggestion, indent=2)), "Suggestion posted.")
                suggestion_card.controls.append(ft.Row([ft.ElevatedButton("Accept suggestion", on_click=accept),
                    ft.TextButton("Post suggestion", on_click=post), ft.TextButton("Reject", on_click=lambda e: result_message({"message": "Suggestion rejected; no changes made."}, ""))], wrap=True))
            if not response.get("suggestions"):
                add("No applicable suggestions returned.")
        elif response.get("status") == "waiting_for_approval":
            awaiting = True
            approval_status = workflow_status(approval=True)
            proposal = card([approval_status,
                ft.Text("Proposed Change", size=20, weight=ft.FontWeight.W_600),
                labeled("Target file", response["target_file"]),
                ft.Column([ft.Text("Analysis", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                           ft.Text(str(response["analysis"]), max_lines=4, overflow=ft.TextOverflow.ELLIPSIS)], spacing=4),
                ft.Text("Generated code", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                code_block(response.get("generated_code", "")),
                labeled("Commit", response["commit_message"]), labeled("Merge Request", response["mr_title"]),
                workflow_details({"analysis": response["analysis"]}), ft.Divider(height=1),
                ft.Text("Branch", weight=ft.FontWeight.W_600)])
            branch = ft.TextField(label="New branch name", value=response.get("branch_name", ""))
            branches = api.get_branches()
            if isinstance(branches, dict):
                proposal.controls.append(ft.Text(branches.get("message", "Unable to load branches."), color=ft.Colors.ERROR))
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
                    branch.disabled = existing.disabled = True
                    approval_status.content.controls[-1] = ft.Text(
                        "Approved" if approved else "Rejected", size=12, weight=ft.FontWeight.W_600)
                    handle(result)
                locked(False)
            approve_button = ft.ElevatedButton("Approve", on_click=lambda e: decision(e, True),
                                               style=ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY, color=ft.Colors.ON_PRIMARY))
            reject_button = ft.OutlinedButton("Reject", on_click=lambda e: decision(e, False),
                                              style=ft.ButtonStyle(color=ft.Colors.ERROR))
            proposal.controls.extend([branch, ft.Text("OR", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                      existing, ft.Row([approve_button, reject_button], wrap=True)])
        else:
            result = response.get("result", {})
            if response.get("mr_url"):
                add("Merge Request created: " + response["mr_url"])
            elif response.get("status") == "rejected":
                add("Workflow rejected. No branch or MR created.")
            else:
                failure = result.get("test_failure")
                if result.get("validation_message"):
                    greeting = pending.strip().lower() in {"hi", "hello", "hey", "hey!", "hi!"}
                    add("Hi! Tell me what you'd like to build, modify, review, or debug." if greeting
                        else result["validation_message"])
                if failure or result.get("analysis") or result.get("test_result") or result.get("security_report"):
                    category = (failure or {}).get("error_category")
                    summaries = {
                        "unsafe_generated_code": "The generated implementation could not be tested safely.",
                        "unsupported_generated_code": "The generated implementation needs a different test environment.",
                        "implementation_failure": "The implementation did not pass its tests. Review the proposed behavior and try again.",
                        "ambiguous_specification": "I need a little more detail about the expected behavior before I can test this change.",
                    }
                    summary = summaries.get(category, "I couldn't complete verification of this change. You can inspect the workflow details.") if failure else (
                        "Security checks need attention. Review the workflow details." if result.get("security_passed") is False
                        else "Here is the workflow summary.")
                    card([ft.Text(summary, selectable=True), workflow_status(result), workflow_details(result)])
                if not result:
                    add(response.get("message", "Request completed."))
        page.update()

    def send(e):
        nonlocal pending
        if busy or awaiting or not (input_box.value or "").strip():
            return
        pending = input_box.value.strip()
        add(pending, user=True)
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
        else:
            add("Hi! Tell me what you'd like to build, modify, review, or debug.")
        update_active()
        page.update()

    send_button = ft.ElevatedButton("Send", on_click=send)
    new_button = ft.OutlinedButton("New chat", on_click=reset)
    change_button = ft.TextButton("Change repository", on_click=lambda e: reset(e, True))
    input_box.on_submit = send
    update_active()
    add("Hi! Tell me what you'd like to build, modify, review, or debug.")
    return ft.Column([
        ft.Text("AI DevOps Agent", size=24, weight=ft.FontWeight.W_600),
        ft.Container(ft.Row([ft.Icon(ft.Icons.CIRCLE, size=8, color=ft.Colors.PRIMARY),
                             active, change_button], spacing=8), padding=8, border_radius=10,
                     bgcolor=ft.Colors.SURFACE_CONTAINER_LOW),
        messages,
        ft.Container(ft.Column([working, ft.Row([input_box, send_button]),
                                ft.Row([new_button], alignment=ft.MainAxisAlignment.END)], spacing=6),
                     padding=12, border_radius=14, bgcolor=ft.Colors.SURFACE_CONTAINER_LOW),
    ], expand=True, spacing=12, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
