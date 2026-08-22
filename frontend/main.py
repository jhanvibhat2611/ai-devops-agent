import flet as ft
from login import show_login
from storage import initialize_database


def main(page: ft.Page):
    page.title = "AI DevOps Agent"
    page.window_width = 500
    page.window_height = 700
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER

    show_login(page)


initialize_database()

ft.app(target=main)