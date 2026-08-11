import flet as ft

from api import review_merge_request, suggest_merge_request


def review_view(page: ft.Page):

    mr_id = ft.TextField(
        label="Merge Request ID",
        width=250
    )

    review_output = ft.TextField(
        multiline=True,
        read_only=True,
        min_lines=20,
        expand=True
    )

    suggestion_output = ft.TextField(
        multiline=True,
        read_only=True,
        min_lines=20,
        expand=True
    )

    def review(e):

        if not mr_id.value:

            page.snack_bar = ft.SnackBar(
                ft.Text("Please enter a Merge Request ID.")
            )
            page.snack_bar.open = True
            page.update()
            return

        result = review_merge_request(mr_id.value)

        if "review" in result:

            review_output.value = result["review"]

        else:

            review_output.value = result.get(
                "message",
                "Unable to generate review."
            )

        page.update()

    def suggest(e):

        if not mr_id.value:

            page.snack_bar = ft.SnackBar(
                ft.Text("Please enter a Merge Request ID.")
            )
            page.snack_bar.open = True
            page.update()
            return

        result = suggest_merge_request(mr_id.value)

        if "suggestion" in result:

            suggestion_output.value = result["suggestion"]

        else:

            suggestion_output.value = result.get(
                "message",
                "Unable to generate code suggestions."
            )

        page.update()

    return ft.Column(
        controls=[
            ft.Text(
                "AI Code Review",
                size=28,
                weight=ft.FontWeight.BOLD
            ),

            ft.Divider(),

            mr_id,

            ft.Row(
                controls=[
                    ft.ElevatedButton(
                        "Generate Review",
                        on_click=review
                    ),

                    ft.ElevatedButton(
                        "Generate Suggestion",
                        on_click=suggest
                    )
                ]
            ),

            ft.Divider(),

            ft.Text(
                "Review",
                size=20,
                weight=ft.FontWeight.BOLD
            ),

            review_output,

            ft.Divider(),

            ft.Text(
                "Code Suggestions",
                size=20,
                weight=ft.FontWeight.BOLD
            ),

            suggestion_output
        ],
        expand=True
    )