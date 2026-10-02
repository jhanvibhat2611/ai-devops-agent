import flet as ft
from api import RepositoryAPI


def suggestions_view(page: ft.Page):

    api = RepositoryAPI(page)
    suggest_merge_request = api.suggest_merge_request
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
        if not mr_id.value:
            page.snack_bar = ft.SnackBar(
                ft.Text("Please enter a Merge Request ID.")
            )
            page.snack_bar.open = True
            page.update()
            return

        result = suggest_merge_request(mr_id.value)

        if "suggestions" in result:
            suggestion_output.value = "\n\n".join(f"File: {item.get('file')}\n{item.get('suggested_code')}\n{item.get('reason')}" for item in result["suggestions"]) or "No suggestions generated."
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