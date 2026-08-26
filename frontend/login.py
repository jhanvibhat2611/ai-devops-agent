import flet as ft

from register import show_register
from api import login_user
from chat import show_chat


def show_login(page: ft.Page):

    username = ft.TextField(
        label="Username",
        width=300
    )

    password = ft.TextField(
        label="Password",
        password=True,
        can_reveal_password=True,
        width=300,
    )

    error_text = ft.Text(
        "",
        color="red",
        size=14
    )

    async def login(e):

        # Clear old error
        error_text.value = ""
        page.update()

        result = login_user(
            username.value,
            password.value
        )

        # Login failed
        if "access_token" not in result:

            error_text.value = result.get(
                "detail",
                "Login failed."
            )

            page.update()
            return

        # Get fresh JWT token
        token = result["access_token"]
        user = result["username"]

        # Save in current page/session
        page.auth_token = token
        page.username = user

        # Save persistently so other views can access it
        await page.shared_preferences.set(
            "access_token",
            token
        )

        await page.shared_preferences.set(
            "username",
            user
        )

        # Debug
        print("\n========== LOGIN JWT ==========")
        print("NEW TOKEN:", token)
        print("USERNAME:", user)
        print("================================\n")

        # Go to chat
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

                ft.Text(
                    "Login",
                    size=18
                ),

                username,

                password,

                error_text,

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