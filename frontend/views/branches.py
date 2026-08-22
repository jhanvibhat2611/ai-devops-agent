import flet as ft

from api import get_branches, create_branch


def branches_view(page):

    branch_name = ft.TextField(
        label="Branch Name"
    )

    reference_branch = ft.TextField(
        label="Reference Branch",
        value="main"
    )

    branch_list = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        expand=True
    )

    def show_branch_details(branch):

        commit = branch.get("commit", {})

        details = ft.Column(
            [
                ft.Text(
                    branch.get("name", "Unknown"),
                    size=24,
                    weight=ft.FontWeight.BOLD,
                ),

                ft.Divider(),

                ft.Text(
                    f"Protected: {branch.get('protected', False)}"
                ),

                ft.Text(
                    f"Default Branch: {branch.get('default', False)}"
                ),

                ft.Text(
                    f"Commit ID: {commit.get('short_id', 'N/A')}"
                ),

                ft.Text(
                    f"Commit Message: {commit.get('title', 'N/A')}"
                ),

                ft.Text(
                    f"Author: {commit.get('author_name', 'N/A')}"
                ),

                ft.Text(
                    f"Created: {commit.get('created_at', 'N/A')}"
                ),
            ],
            spacing=12,
        )

        dialog = ft.AlertDialog(
            title=ft.Text("Branch Details"),
            content=ft.Container(
                content=details,
                width=500,
                padding=10,
            ),
        )

        page.overlay.append(dialog)
        dialog.open = True
        page.update()

    def load_branches(e=None):

        branch_list.controls.clear()

        branches = get_branches()

        if isinstance(branches, dict) and "error" in branches:

            branch_list.controls.append(
                ft.Text(
                    f"Error loading branches: "
                    f"{branches.get('message')}"
                )
            )

            page.update()
            return

        for branch in branches:

            branch_list.controls.append(
                ft.Card(
                    content=ft.ListTile(
                        leading=ft.Icon(
                            ft.Icons.ACCOUNT_TREE
                        ),

                        title=ft.Text(
                            branch.get("name", "Unknown")
                        ),

                        subtitle=ft.Text(
                            "Click to view branch details"
                        ),

                        trailing=ft.Icon(
                            ft.Icons.ARROW_FORWARD_IOS
                        ),

                        on_click=lambda e, b=branch: (
                            show_branch_details(b)
                        ),
                    )
                )
            )

        page.update()

    def create(e):

        response = create_branch(
            branch_name.value,
            reference_branch.value
        )

        if isinstance(response, dict) and "error" in response:

            page.snack_bar = ft.SnackBar(
                ft.Text(
                    f"Error: {response.get('message')}"
                )
            )

        else:

            page.snack_bar = ft.SnackBar(
                ft.Text("Branch created successfully!")
            )

            branch_name.value = ""

        page.snack_bar.open = True

        load_branches()

        page.update()

    return ft.Column(
        [
            ft.Text(
                "Branches",
                size=28,
                weight=ft.FontWeight.BOLD,
            ),

            ft.Divider(),

            ft.Row(
                [
                    branch_name,

                    reference_branch,

                    ft.ElevatedButton(
                        "Create",
                        on_click=create
                    ),
                ]
            ),

            ft.ElevatedButton(
                "Load Branches",
                on_click=load_branches,
            ),

            ft.Text(
                "Available Branches",
                size=18,
                weight=ft.FontWeight.BOLD,
            ),

            branch_list,
        ],
        expand=True,
    )