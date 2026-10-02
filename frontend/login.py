import flet as ft

from register import show_register

from api import (
    login_user
)

from chat import show_chat


# ============================================================
# LOGIN
# ============================================================

def show_login(
    page: ft.Page
):

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

    # ========================================================
    # LOGIN HANDLER
    # ========================================================

    async def login(e):

        error_text.value = ""

        page.update()

        # ----------------------------------------------------
        # Basic validation
        # ----------------------------------------------------

        entered_username = (
            username.value
            or ""
        ).strip()

        entered_password = (
            password.value
            or ""
        )

        if (
            not entered_username
            or not entered_password
        ):

            error_text.value = (
                "Please enter username and password."
            )

            page.update()
            return

        # ----------------------------------------------------
        # Login API
        # ----------------------------------------------------

        result = login_user(
            entered_username,
            entered_password
        )

        # ----------------------------------------------------
        # Login failed
        # ----------------------------------------------------

        if "access_token" not in result:

            error_text.value = result.get(
                "detail",
                "Invalid username or password."
            )

            page.update()
            return

        # ----------------------------------------------------
        # Login successful
        # ----------------------------------------------------

        token = result[
            "access_token"
        ]

        user = result[
            "username"
        ]

        # Save in current session
        page.auth_token = token
        page.username = user
        for name in ("gitlab_project_id", "gitlab_project_name", "gitlab_default_branch", "gitlab_clone_url"):
            setattr(page, name, None)

        # Persist session values
        await page.shared_preferences.set(
            "access_token",
            token
        )

        await page.shared_preferences.set(
            "username",
            user
        )

        show_chat(page)

    # ========================================================
    # OPEN REGISTER SCREEN
    # ========================================================

    def open_register(e):

        show_register(
            page,
            show_login
        )

    # ========================================================
    # LOGIN UI
    # ========================================================

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

                ft.TextButton(
                    "Don't have an account? Register",
                    on_click=open_register
                ),
            ],
            horizontal_alignment=(
                ft.CrossAxisAlignment.CENTER
            ),
            spacing=20,
        )
    )