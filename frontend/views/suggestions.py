import flet as ft
from api import suggest_merge_request


def suggestions_view(page: ft.Page):

    mr_id = ft.TextField(
        label="Merge Request ID",
        width=250
    )

    suggestion_output = ft.TextField(
        multiline=True,
        read_only=True,
        min_lines=20,
        expand=True
    )

    def generate_suggestions(e):
        result = suggest_merge_request(mr_id.value)
        print(result)
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
                "Unable to generate suggestions."
            )

        page.update()

    return ft.Column(
        controls=[
            ft.Text(
                "AI Suggestions",
                size=28,
                weight=ft.FontWeight.BOLD
            ),

            ft.Divider(),

            mr_id,

            ft.ElevatedButton(
                "Generate Suggestions",
                on_click=generate_suggestions
            ),

            ft.Divider(),

            ft.Text(
                "Suggestions",
                size=20,
                weight=ft.FontWeight.BOLD
            ),

            suggestion_output
        ],
        expand=True
    )