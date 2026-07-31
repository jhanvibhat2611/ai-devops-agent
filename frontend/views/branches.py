import flet as ft

from api import get_branches, create_branch


def branches_view(page):

    branch_name = ft.TextField(label="Branch Name")

    reference_branch = ft.TextField(
        label="Reference Branch",
        value="main"
    )

    branch_list = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        expand=True
    )

    def load_branches(e=None):

        branch_list.controls.clear()

        branches = get_branches()

        for branch in branches:
            branch_list.controls.append(
                ft.Text(branch["name"])
            )



    def create(e):

        response = create_branch(
            branch_name.value,
            reference_branch.value
        )





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