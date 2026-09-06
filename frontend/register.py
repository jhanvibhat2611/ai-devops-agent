import flet as ft

from api import register_user


def show_register(
    page: ft.Page,
    show_login
):

    # ============================================================
    # FORM FIELDS
    # ============================================================

    username = ft.TextField(
        label="Username",
        width=320
    )

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

    gitlab_token = ft.TextField(
        label="GitLab Access Token",
        password=True,
        can_reveal_password=True,
        width=320,
    )

    error_text = ft.Text(
        "",
        color="red",
        size=14
    )

    # ============================================================
    # REGISTER
    # ============================================================

    def register(e):

        error_text.value = ""

        # --------------------------------------------------------
        # Read form values
        # --------------------------------------------------------

        new_username = (
            username.value
            or ""
        ).strip()

        new_password = (
            password.value
            or ""
        )

        confirmed_password = (
            confirm_password.value
            or ""
        )

        new_gitlab_token = (
            gitlab_token.value
            or ""
        ).strip()

        # --------------------------------------------------------
        # Required-field validation
        # --------------------------------------------------------

        if not all(
            [
                new_username,
                new_password,
                confirmed_password,
                new_gitlab_token
            ]
        ):

            error_text.value = (
                "Please fill in all fields."
            )

            page.update()
            return

        # --------------------------------------------------------
        # Password confirmation
        # --------------------------------------------------------

        if (
            new_password
            != confirmed_password
        ):

            error_text.value = (
                "Passwords do not match."
            )

            page.update()
            return

        # --------------------------------------------------------
        # Backend registration
        # --------------------------------------------------------

        try:

            result = register_user(
                new_username,
                new_password,
                new_gitlab_token
            )

        except Exception as error:

            print(
                "REGISTRATION ERROR:",
                error
            )

            error_text.value = (
                "Unable to connect to the backend."
            )

            page.update()
            return

        # --------------------------------------------------------
        # Backend rejected registration
        # --------------------------------------------------------

        if result.get(
            "error"
        ):

            error_text.value = result.get(
                "message",
                "Registration failed."
            )

            page.update()
            return

        # --------------------------------------------------------
        # Registration successful
        # --------------------------------------------------------

        page.snack_bar = ft.SnackBar(
            ft.Text(
                "Registration successful. "
                "Please log in."
            )
        )

        page.snack_bar.open = True

        show_login(
            page
        )

        page.update()

    # ============================================================
    # UI
    # ============================================================

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
                    "Create Account",
                    size=20,
                    weight=ft.FontWeight.BOLD,
                ),

                username,

                password,

                confirm_password,

                gitlab_token,

                error_text,

                ft.ElevatedButton(
                    "Create Account",
                    on_click=register,
                    width=320,
                ),

                ft.TextButton(
                    "Already have an account? Login",
                    on_click=lambda e: show_login(
                        page
                    )
                ),
            ],
            horizontal_alignment=(
                ft.CrossAxisAlignment.CENTER
            ),
            spacing=15,
        )
    )