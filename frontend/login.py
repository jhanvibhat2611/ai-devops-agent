import flet as ft
from register import show_register
from storage import user_exists, verify_user
from chat import show_chat

def show_login(page: ft.Page):

    username = ft.TextField(label="Username", width=300)
    password = ft.TextField(
        label="Password",
        password=True,
        can_reveal_password=True,
        width=300,
    )

    def login(e):

        if not user_exists(username.value):
            show_register(page)
            return

        if not verify_user(username.value, password.value):
            page.snack_bar = ft.SnackBar(
                ft.Text("Incorrect Password!")
            )

            page.snack_bar.open = True
            page.update()
            return

        show_chat(page)

    page.clean()

    page.add(
        ft.Column(
            [
                ft.Text(
                    "AI DevOps Agent",
                    size=28,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Text("Login", size=18),

                username,
                password,

                ft.ElevatedButton(
                    "Login",
                    on_click=login,
                    width=300,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=20,
        )
    )