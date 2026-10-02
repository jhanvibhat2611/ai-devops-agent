import flet as ft

from api import RepositoryAPI


def merge_requests_view(page: ft.Page):

    api = RepositoryAPI(page)
    get_merge_requests = api.get_merge_requests
    create_merge_request = api.create_merge_request
    get_merge_request = api.get_merge_request
    get_merge_request_approval_history = api.get_merge_request_approval_history
    get_mr_changes = api.get_mr_changes
    page.title = "GitLab Merge Requests"

    # ---------------------------------------------------------
    # Fields (Forms)
    # ---------------------------------------------------------

    source_branch = ft.TextField(
        label="Source Branch",
        width=180,
    )

    target_branch = ft.TextField(
        label="Target Branch",
        value=getattr(page, "gitlab_default_branch", None) or "main",
        width=180,
    )

    title = ft.TextField(
        label="Merge Request Title",
        width=370,
    )

    mr_id = ft.TextField(
        label="Merge Request ID",
        width=180,
    )

    # ---------------------------------------------------------
    # MR Details & History Output (Left Panel)
    # ---------------------------------------------------------

    mr_detail_output = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=10,
    )

    # ---------------------------------------------------------
    # Merge Requests List Cards (Right Panel)
    # ---------------------------------------------------------

    cards_output = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=10,
    )

    status_text = ft.Text(
        "",
        size=14,
    )

    # ---------------------------------------------------------
    # Load ALL Merge Requests
    # ---------------------------------------------------------

    def load_merge_requests(e=None):
        cards_output.controls.clear()
        status_text.value = "Loading..."
        page.update()

        try:
            merge_requests = get_merge_requests()

            if not isinstance(merge_requests, list):
                cards_output.controls.append(
                    ft.Text(
                        "Unable to fetch merge requests.",
                        color=ft.Colors.RED,
                    )
                )
                status_text.value = ""
                page.update()
                return

            if not merge_requests:
                cards_output.controls.append(
                    ft.Text(
                        "No merge requests found.",
                        size=16,
                    )
                )
                status_text.value = "0 merge request(s) found"
                page.update()
                return

            for mr in merge_requests:
                iid = mr.get("iid", "N/A")
                mr_title = mr.get("title", "No title")
                state = mr.get("state", "unknown")
                author = mr.get("author", {})
                author_name = author.get("name", "Unknown")
                source = mr.get("source_branch", "N/A")
                target = mr.get("target_branch", "N/A")
                web_url = mr.get("web_url", "")

                if state == "opened":
                    state_color = ft.Colors.GREEN
                elif state == "merged":
                    state_color = ft.Colors.BLUE
                elif state == "closed":
                    state_color = ft.Colors.RED
                else:
                    state_color = ft.Colors.GREY

                actions = []
                if web_url:
                    actions.append(
                        ft.TextButton(
                            "Open in GitLab",
                            on_click=lambda e, url=web_url: page.launch_url(url),
                        )
                    )

                mr_card = ft.Card(
                    elevation=2,
                    content=ft.Container(
                        padding=15,
                        content=ft.Column(
                            spacing=8,
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Text(
                                            f"MR !{iid}",
                                            weight=ft.FontWeight.BOLD,
                                            size=16,
                                        ),
                                        ft.Text(
                                            mr_title,
                                            size=16,
                                            expand=True,
                                        ),
                                        ft.Container(
                                            padding=5,
                                            border_radius=5,
                                            bgcolor=state_color,
                                            content=ft.Text(
                                                state.upper(),
                                                color=ft.Colors.WHITE,
                                                size=11,
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                        ),
                                    ]
                                ),
                                ft.Divider(),
                                ft.Text(f"Author: {author_name}"),
                                ft.Row(
                                    controls=[
                                        ft.Text(
                                            f"Source: {source}",
                                            expand=True,
                                        ),
                                        ft.Text("→"),
                                        ft.Text(
                                            f"Target: {target}",
                                            expand=True,
                                        ),
                                    ]
                                ),
                                ft.Row(controls=actions),
                            ],
                        ),
                    ),
                )
                cards_output.controls.append(mr_card)

            status_text.value = f"{len(merge_requests)} merge request(s) found"

        except Exception as ex:
            cards_output.controls.append(
                ft.Text(
                    f"Error loading merge requests: {ex}",
                    color=ft.Colors.RED,
                )
            )
            status_text.value = ""

        page.update()

    # ---------------------------------------------------------
    # Search / Filter
    # ---------------------------------------------------------

    def filter_merge_requests(e):
        search_text = e.control.value.lower().strip()

        for card in cards_output.controls:
            if not isinstance(card, ft.Card):
                continue

            try:
                column = card.content.content
                text_values = []

                for control in column.controls:
                    if isinstance(control, ft.Text) and control.value:
                        text_values.append(control.value.lower())
                    elif isinstance(control, ft.Row):
                        for child in control.controls:
                            if isinstance(child, ft.Text) and child.value:
                                text_values.append(child.value.lower())

                full_text = " ".join(text_values)
                card.visible = search_text in full_text
            except Exception:
                card.visible = True

        page.update()

    search_box = ft.TextField(
        label="Search merge requests",
        prefix_icon=ft.Icons.SEARCH,
        on_change=filter_merge_requests,
        expand=True,
    )

    refresh_button = ft.ElevatedButton(
        "Refresh",
        icon=ft.Icons.REFRESH,
        on_click=load_merge_requests,
    )

    # ---------------------------------------------------------
    # Create & View Callbacks
    # ---------------------------------------------------------

    def create(e):
        response = create_merge_request(
            source_branch.value,
            target_branch.value,
            title.value,
        )

        page.snack_bar = ft.SnackBar(
            ft.Text("Merge Request created successfully!" if response.get("iid") and not response.get("error") else response.get("message", "Creation failed."))
        )
        page.snack_bar.open = True
        load_merge_requests()

    def view_merge_request(e):
        mr_detail_output.controls.clear()
        mr = get_merge_request(mr_id.value)

        if not mr or "error" in mr:
            mr_detail_output.controls.append(
                ft.Text("Merge Request not found.", color=ft.Colors.RED)
            )
        else:
            # 1. Author mapping
            author_obj = mr.get("author") or {}
            author_display = (
                f"{author_obj.get('name', '')} (@{author_obj.get('username', '')})"
                if author_obj.get("username")
                else "N/A"
            )

            # 2. Merged by mapping
            merged_by_obj = mr.get("merged_by") or mr.get("merge_user") or {}
            merged_by_display = (
                merged_by_obj.get("name", "Unknown")
                if isinstance(merged_by_obj, dict) and merged_by_obj
                else "Not merged"
            )
            merged_at = mr.get("merged_at") or mr.get("merge_at") or {}

            # 3. Formatted fields
            description_display = mr.get("description") or "No description provided"
            created_at_raw = mr.get("created_at", "")
            created_at_display = (
                created_at_raw.replace("T", " ").split(".")[0]
                if created_at_raw
                else "N/A"
            )

            state = mr.get("state", "unknown")
            state_color = (
                ft.Colors.GREEN
                if state == "opened"
                else (
                    ft.Colors.BLUE
                    if state == "merged"
                    else ft.Colors.RED if state == "closed" else ft.Colors.GREY
                )
            )

            mr_detail_output.controls.append(
                ft.Card(
                    elevation=2,
                    content=ft.Container(
                        padding=12,
                        content=ft.Column(
                            spacing=6,
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Text(
                                            f"MR #{mr.get('iid', '')}",
                                            weight=ft.FontWeight.BOLD,
                                            size=16,
                                        ),
                                        ft.Container(
                                            padding=ft.Padding(left=6, top=2, right=6, bottom=2),

                                            border_radius=4,
                                            bgcolor=state_color,
                                            content=ft.Text(
                                                state.upper(),
                                                color=ft.Colors.WHITE,
                                                size=11,
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                        ),
                                    ]
                                ),
                                ft.Divider(),
                                ft.Text(
                                    f"Title: {mr.get('title', 'No title')}",
                                    weight=ft.FontWeight.W_500,
                                ),
                                ft.Text(f"Author: {author_display}"),
                                ft.Text(f"Created at: {created_at_display}"),
                                ft.Text(f"Merged by: {merged_by_display}"),
                                ft.Text(f"Merged at: {merged_at}"),
                                ft.Text(
                                    f"Branches: {mr.get('source_branch', '')} → {mr.get('target_branch', '')}"
                                ),
                                ft.Text(
                                    f"Description: {description_display}",
                                    italic=(mr.get("description") is None),
                                ),
                            ],
                        ),
                    ),
                )
            )

            mr_detail_output.controls.append(
                ft.Text(
                    "Changes in code",
                    size=16,
                    weight=ft.FontWeight.BOLD,
                )
            )
            changes_done = get_mr_changes(mr_id.value)
            if changes_done.get("error"):
                mr_detail_output.controls.append(ft.Text(changes_done.get("message", "Unable to load changes.")))
            for changed in changes_done.get("files", []):
                mr_detail_output.controls.append(ft.Card(content=ft.Container(padding=8, content=ft.Column([
                    ft.Text(changed.get("new_path") or changed.get("old_path"), weight=ft.FontWeight.BOLD),
                    ft.Text("Original code"), ft.Text(changed.get("original_code") or "(File absent)", selectable=True),
                    ft.Text("Modified code"), ft.Text(changed.get("modified_code") or "(File absent)", selectable=True),
                    ft.Text("Git diff"), ft.Text(changed.get("diff_git", ""), selectable=True),
                ]))))
            if not changes_done.get("files") and not changes_done.get("error"):
                mr_detail_output.controls.append(ft.Text("No changed files."))

            mr_detail_output.controls.append(
                ft.Text(
                    "Approval History",
                    size=16,
                    weight=ft.FontWeight.BOLD,
                )
            )

            approval_history = get_merge_request_approval_history(mr.get("iid"))
            approvals = approval_history.get("approvals", [])

            if approvals:
                for approval in approvals:
                    status = (
                        "✅ Approved"
                        if approval.get("status") == "approved"
                        else "❌ Rejected"
                    )
                    mr_detail_output.controls.append(
                        ft.Card(
                            content=ft.Container(
                                padding=8,
                                content=ft.Column(
                                    [
                                        ft.Text(
                                            status, weight=ft.FontWeight.BOLD
                                        ),
                                        ft.Text(
                                            f"User: {approval.get('username', '')}"
                                        ),
                                        ft.Text(
                                            f"Time: {approval.get('approved_at', '')}"
                                        ),
                                    ]
                                ),
                            )
                        )
                    )
            else:
                mr_detail_output.controls.append(
                    ft.Text("No approval history found.")
                )

        page.update()
    # ---------------------------------------------------------
    # Left Column: Forms and Details Menu
    # ---------------------------------------------------------

    left_menu_panel = ft.Container(
        width=380,
        padding=10,
        content=ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Text(
                    "Merge Requests",
                    size=24,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Divider(),
                ft.Row(controls=[source_branch, target_branch]),
                title,
                ft.ElevatedButton(
                    "Create Merge Request",
                    icon=ft.Icons.ADD,
                    on_click=create,
                ),
                ft.Divider(),
                ft.Row(
                    controls=[
                        mr_id,
                        ft.ElevatedButton(
                            "View MR",
                            icon=ft.Icons.SEARCH,
                            on_click=view_merge_request,
                        ),
                    ]
                ),
                ft.Divider(),
                mr_detail_output,
            ],
        ),
    )

    # ---------------------------------------------------------
    # Right Column: Search Box & Merge Request Cards
    # ---------------------------------------------------------

    right_content_panel = ft.Container(
        expand=True,
        padding=10,
        content=ft.Column(
            expand=True,
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(
                            "GitLab Merge Requests",
                            size=24,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Container(expand=True),
                        refresh_button,
                    ]
                ),
                ft.Row(
                    controls=[
                        search_box,
                        status_text,
                    ]
                ),
                ft.Divider(),
                cards_output,
            ],
        ),
    )

    # ---------------------------------------------------------
    # Return Single Layout
    # ---------------------------------------------------------

    main_view = ft.Row(
        expand=True,
        controls=[
            left_menu_panel,
            ft.VerticalDivider(width=1),
            right_content_panel,
        ],
    )

    load_merge_requests()

    return main_view