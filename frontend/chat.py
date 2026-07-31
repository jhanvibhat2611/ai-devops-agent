import flet as ft


def show_chat(page: ft.Page):

    user_input = ft.TextField(
        hint_text="Ask something...",
        expand=True,
    )

    chat_history = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    def send_message(e):

        if user_input.value.strip() == "":
            return

        # Display user message
        chat_history.controls.append(
            ft.Text(f"You: {user_input.value}")
        )

        # Placeholder AI response
        chat_history.controls.append(
            ft.Text("AI: Response will appear here...")
        )

        user_input.value = ""

        page.update()

    page.clean()

    page.add(
        ft.Column(
            [
                ft.Text(
                    "AI DevOps Agent",
                    size=28,
                    weight=ft.FontWeight.BOLD,
                ),

                ft.Divider(),

                chat_history,

                ft.Row(
                    [
                        user_input,
                        ft.ElevatedButton(
                            "Send",
                            on_click=send_message,
                        ),
                    ]
                ),
            ],
            expand=True,
        )
    )