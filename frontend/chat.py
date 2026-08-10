import flet as ft
from views.home import home_view
from views.branches import branches_view
from views.merge_requests import merge_requests_view
from views.review import review_view
from views.suggestions import suggestions_view

def show_chat(page: ft.Page):

    content = ft.Container(
        expand=True,
        content=home_view(page)
    )

    def change_view(e):

        index = e.control.selected_index

        if index == 0:
            content.content = home_view(page)

        elif index == 1:
            content.content = branches_view(page)


        elif index == 2:
            content.content = merge_requests_view(page)

        elif index == 3:
            content.content = review_view(page)

        elif index == 4:
            content.content = suggestions_view(page)

        page.update()

    navigation = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        on_change=change_view,
        destinations=[
            ft.NavigationRailDestination(
                icon=ft.Icons.HOME,
                label="Home"
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.ACCOUNT_TREE,
                label="Branches"
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.MERGE_TYPE,
                label="Merge Requests"
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.RATE_REVIEW,
                label="AI Review"
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.AUTO_AWESOME,
                label="Suggestions"
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.SEARCH,
                label="Search"
            ),
        ]
    )

    page.clean()

    page.add(
        ft.Row(
            controls=[
                navigation,
                ft.VerticalDivider(),
                content
            ],
            expand=True
        )
    )