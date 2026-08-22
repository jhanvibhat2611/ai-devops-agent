import flet as ft
from storage import create_user
from chat import show_chat

def show_register(page: ft.Page):

    username = ft.TextField(label="Username", width=320)

    password = ft.TextField(
        label="Password",
        password=True,
        can_reveal_password=True,
        width=320,
    )

    confirm_password = ft.TextField(
        label="Confirm Password",
        password=True,
        can_reveal_password=True,
        width=320,
    )

    gitlab_username = ft.TextField(
        label="GitLab Username",
        width=320,
    )

    gitlab_token = ft.TextField(
        label="GitLab Personal Access Token",
        password=True,
        can_reveal_password=True,
        width=320,
    )

    def register(e):
        if password.value != confirm_password.value:
            page.snack_bar = ft.SnackBar(
                ft.Text("Passwords do not match!")
            )
            page.snack_bar.open = True
            page.update()
            return

        create_user(
            username.value,
            password.value,
            gitlab_username.value,
            gitlab_token.value,
        )
        show_chat(page)

        page.snack_bar = ft.SnackBar(
            ft.Text("Registration Successful!")
        )
        page.snack_bar.open = True
        page.update()

    page.clean()

    page.add(
        ft.Column(
            [
                ft.Text(
                    "Create Account",
                    size=28,
                    weight=ft.FontWeight.BOLD,
                ),

                username,
                password,
                confirm_password,
                gitlab_username,
                gitlab_token,

                ft.ElevatedButton(
                    "Register",
                    on_click=register,
                    width=320,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=15,
        )
    )