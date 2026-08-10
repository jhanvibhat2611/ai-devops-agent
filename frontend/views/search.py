import flet as ft

from api import search_merge_requests


def search_view(page: ft.Page):

    search_box = ft.TextField(
        label="Search Merge Requests",
        hint_text="Enter a keyword...",
        expand=True
    )

    results = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        expand=True
    )

    def search(e):

        results.controls.clear()

        if not search_box.value.strip():
            results.controls.append(
                ft.Text("Please enter a search query.")
            )
            page.update()
            return

        response = search_merge_requests(
            search_box.value.strip()
        )

        if not response:
            results.controls.append(
                ft.Text("No results found.")
            )

        else:
            for mr in response:

                results.controls.append(
                    ft.Card(
                        content=ft.Container(
                            padding=15,
                            content=ft.Column(
                                [
                                    ft.Text(
                                        f"MR #{mr['mr_id']}",
                                        size=18,
                                        weight=ft.FontWeight.BOLD
                                    ),
                                    ft.Text(
                                        f"Title: {mr['title']}"
                                    ),
                                    ft.Text(
                                        f"Author: {mr['author']}"
                                    ),
                                    ft.Text(
                                        f"State: {mr['state']}"
                                    ),
                                ]
                            )
                        )
                    )
                )

        page.update()

    return ft.Column(
        [
            ft.Text(
                "Search Merge Requests",
                size=28,
                weight=ft.FontWeight.BOLD
            ),

            ft.Divider(),

            ft.Row(
                [
                    search_box,

                    ft.ElevatedButton(
                        "Search",
                        on_click=search
                    )
                ]
            ),

            ft.Divider(),

            results
        ],
        expand=True
    )