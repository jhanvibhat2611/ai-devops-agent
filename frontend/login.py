import flet as ft

from register import show_register

from api import (
    login_user,
    get_gitlab_projects
)

from chat import show_chat


# ============================================================
# REPOSITORY SELECTION
# ============================================================

def show_repository_selection(
    page: ft.Page
):

    repository_dropdown = ft.Dropdown(
        label="Select GitLab Repository",
        width=400,
        options=[]
    )

    status_text = ft.Text(
        "",
        size=14
    )

    projects_by_id = {}

    # ========================================================
    # LOAD REPOSITORIES
    # ========================================================

    result = get_gitlab_projects(
        page.auth_token
    )

    if result.get("error"):

        status_text.value = (
            "Unable to load GitLab repositories.\n"
            f"{result.get('message', '')}"
        )

    else:

        projects = result.get(
            "projects",
            []
        )

        for project in projects:

            project_id = str(
                project["id"]
            )

            projects_by_id[
                project_id
            ] = project

            repository_dropdown.options.append(
                ft.dropdown.Option(
                    key=project_id,
                    text=project[
                        "path_with_namespace"
                    ]
                )
            )

        if not projects:

            status_text.value = (
                "No GitLab repositories were found "
                "for this account."
            )

    # ========================================================
    # CONTINUE TO APPLICATION
    # ========================================================

    async def continue_to_agent(e):

        selected_project_id = (
            repository_dropdown.value
        )

        if not selected_project_id:

            status_text.value = (
                "Please select a repository."
            )

            page.update()
            return

        selected_project = (
            projects_by_id.get(
                selected_project_id
            )
        )

        if not selected_project:

            status_text.value = (
                "Unable to find selected repository."
            )

            page.update()
            return

        # ----------------------------------------------------
        # Save repository information in page/session
        # ----------------------------------------------------

        page.gitlab_project_id = (
            selected_project["id"]
        )

        page.gitlab_project_name = (
            selected_project[
                "path_with_namespace"
            ]
        )

        page.gitlab_default_branch = (
            selected_project.get(
                "default_branch"
            )
        )

        # ----------------------------------------------------
        # Persist repository selection
        # ----------------------------------------------------

        await page.shared_preferences.set(
            "gitlab_project_id",
            str(
                selected_project["id"]
            )
        )

        await page.shared_preferences.set(
            "gitlab_project_name",
            selected_project[
                "path_with_namespace"
            ]
        )

        default_branch = (
            selected_project.get(
                "default_branch"
            )
            or ""
        )

        await page.shared_preferences.set(
            "gitlab_default_branch",
            default_branch
        )

        print(
            "\n========== REPOSITORY SELECTED =========="
        )

        print(
            "Project ID:",
            selected_project["id"]
        )

        print(
            "Repository:",
            selected_project[
                "path_with_namespace"
            ]
        )

        print(
            "Default branch:",
            default_branch
        )

        print(
            "=========================================\n"
        )

        show_chat(
            page
        )

    # ========================================================
    # UI
    # ========================================================

    page.clean()

    page.add(
        ft.Column(
            [
                ft.Text(
                    "AI DevOps Agent",
                    size=28,
                    weight=ft.FontWeight.BOLD
                ),

                ft.Text(
                    "Select Repository",
                    size=20,
                    weight=ft.FontWeight.BOLD
                ),

                ft.Text(
                    "Choose the GitLab repository "
                    "you want the agent to work on."
                ),

                repository_dropdown,

                status_text,

                ft.ElevatedButton(
                    "Continue",
                    on_click=continue_to_agent,
                    width=400
                )
            ],
            horizontal_alignment=(
                ft.CrossAxisAlignment.CENTER
            ),
            spacing=20
        )
    )


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

        # Persist session values
        await page.shared_preferences.set(
            "access_token",
            token
        )

        await page.shared_preferences.set(
            "username",
            user
        )

        print(
            "\n========== LOGIN JWT =========="
        )

        print(
            "USERNAME:",
            user
        )

        print(
            "================================\n"
        )

        # ----------------------------------------------------
        # Repository selection before agent
        # ----------------------------------------------------

        show_repository_selection(
            page
        )

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