import flet as ft
from api import get_home


def home_view(page):

    data = get_home()

    return ft.Column(
        [
            ft.Text(
                "Home",
                size=28,
                weight=ft.FontWeight.BOLD,
            ),
            ft.Divider(),
            ft.Text(data["message"])
        ],
        expand=True
    )