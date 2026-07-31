import flet as ft

from api import (
    get_merge_requests,
    create_merge_request,
    get_merge_request,
)


def merge_requests_view(page: ft.Page):

    source_branch = ft.TextField(
        label="Source Branch",
        width=200,
    )

    target_branch = ft.TextField(
        label="Target Branch",
        value="main",
        width=200,
    )

    title = ft.TextField(
        label="Merge Request Title",
        width=400,
    )

    mr_id = ft.TextField(
        label="Merge Request ID",
        width=200,
    )

    output = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    def load_merge_requests(e=None):

        output.controls.clear()

        merge_requests = get_merge_requests()

        if isinstance(merge_requests, list):

            for mr in merge_requests:

                output.controls.append(
                    ft.Card(
                        content=ft.Container(
                            padding=10,
                            content=ft.Column(
                                [
                                    ft.Text(
                                        f"MR #{mr['iid']}",
                                        weight=ft.FontWeight.BOLD,
                                        size=18,
                                    ),
                                    ft.Text(f"Title: {mr['title']}"),
                                    ft.Text(f"State: {mr['state']}"),
                                    ft.Text(f"Author: {mr['author']['name']}"),
                                ]
                            ),
                        )
                    )
                )

        else:
            output.controls.append(
                ft.Text("Unable to fetch merge requests.")
            )



    def create(e):

        response = create_merge_request(
            source_branch.value,
            target_branch.value,
            title.value,
        )

        page.snack_bar = ft.SnackBar(
            ft.Text("Merge Request created successfully!")
        )
        page.snack_bar.open = True

        load_merge_requests()

    def view_merge_request(e):

        output.controls.clear()

        mr = get_merge_request(mr_id.value)

        if "error" in mr:

            output.controls.append(
                ft.Text("Merge Request not found.")
            )

        else:

            output.controls.append(
                ft.Card(
                    content=ft.Container(
                        padding=10,
                        content=ft.Column(
                            [
                                ft.Text(
                                    f"MR #{mr['iid']}",
                                    weight=ft.FontWeight.BOLD,
                                    size=18,
                                ),
                                ft.Text(f"Title: {mr['title']}"),
                                ft.Text(f"State: {mr['state']}"),
                                ft.Text(f"Description: {mr['description']}"),
                            ]
                        ),
                    )
                )
            )

        page.update()



    return ft.Column(
        controls=[
            ft.Text(
                "Merge Requests",
                size=28,
                weight=ft.FontWeight.BOLD,
            ),

            ft.Divider(),

            ft.Row(
                controls=[
                    source_branch,
                    target_branch,
                ]
            ),

            title,

            ft.ElevatedButton(
                "Create Merge Request",
                on_click=create,
            ),

            ft.Divider(),

            ft.Row(
                controls=[
                    mr_id,
                    ft.ElevatedButton(
                        "View Merge Request",
                        on_click=view_merge_request,
                    ),
                ]
            ),

            ft.Divider(),

            output,
        ],
        expand=True,
    )