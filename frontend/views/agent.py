import flet as ft

from api import start_chat, send_chat_decision, post_ai_review


def agent_view(page):

    messages = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=10
    )

    input_box = ft.TextField(
        hint_text="Ask the AI DevOps Agent...",
        expand=True
    )

    current_thread_id = None

    def add_message(text, is_user=False):

        messages.controls.append(
            ft.Container(
                content=ft.Text(
                    text,
                    size=15
                ),
                padding=10,
                border_radius=10,
                bgcolor=(
                    ft.Colors.BLUE_100
                    if is_user
                    else ft.Colors.GREY_200
                ),
                alignment=(
                    ft.alignment.Alignment(1, 0)
                    if is_user
                    else ft.alignment.Alignment(-1, 0)
                )
            )
        )

    def send_message(e):

        nonlocal current_thread_id

        message = input_box.value.strip()

        if not message:
            return

        add_message(
            f"You: {message}",
            is_user=True
        )

        input_box.value = ""
        page.update()

        response = start_chat(message)

        # ========================================================
        # AI CODE REVIEW
        # ========================================================

        if response.get("type") == "review":

            mr_id = response.get("mr_iid")

            review = response.get(
                "review",
                "Unable to generate review."
            )

            add_message(
                f"AI Code Review:\n\n{review}"
            )

            def post_review(e):

                result = post_ai_review(mr_id)

                if result.get("status") == "posted":

                    add_message(
                        "✅ AI review successfully posted to GitLab."
                    )

                else:

                    add_message(
                        "❌ Failed to post AI review to GitLab.\n\n"
                        f"{result.get('message', result)}"
                    )

                page.update()

            messages.controls.append(
                ft.ElevatedButton(
                    "Post Review to GitLab",
                    on_click=post_review
                )
            )

            page.update()
            return

        # ========================================================
        # AI CODE SUGGESTION
        # ========================================================

        if response.get("type") == "suggestion":

            suggestion = response.get(
                "suggestion",
                "Unable to generate suggestions."
            )

            add_message(
                f"AI Code Suggestions:\n\n{suggestion}"
            )

            page.update()
            return

        # ========================================================
        # EXISTING LANGGRAPH WORKFLOW
        # ========================================================

        if response.get("status") == "waiting_for_approval":

            current_thread_id = response["thread_id"]

            proposal = (
                "AI DevOps Agent:\n\n"
                f"Analysis:\n{response['analysis']}\n\n"
                f"Branch: {response['branch_name']}\n"
                f"Commit: {response['commit_message']}\n"
                f"MR Title: {response['mr_title']}"
            )

            add_message(proposal)

            approval_buttons = ft.Row(
                [
                    ft.ElevatedButton(
                        "Approve",
                        on_click=approve
                    ),
                    ft.OutlinedButton(
                        "Reject",
                        on_click=reject
                    )
                ]
            )

            messages.controls.append(
                approval_buttons
            )

        else:

            result = response.get("result", {})

            if result.get("request_valid") is False:

                validation_message = result.get(
                    "validation_message",
                    "Please provide a valid development task."
                )

                add_message(
                    f"AI DevOps Agent:\n\n{validation_message}"
                )

            else:

                add_message(
                    f"AI DevOps Agent:\n{result}"
                )

        page.update()

    def approve(e):

        nonlocal current_thread_id

        if not current_thread_id:
            return

        response = send_chat_decision(
            current_thread_id,
            True
        )

        mr_url = response.get("mr_url")

        if mr_url:

            message = (
                "AI DevOps Agent:\n\n"
                "✅ Workflow approved.\n\n"
                f"Merge Request created:\n{mr_url}"
            )

        else:

            message = (
                "AI DevOps Agent:\n\n"
                "⚠️ Workflow was approved, but the Merge Request "
                "could not be created."
            )

        add_message(message)

        current_thread_id = None

        page.update()

    def reject(e):

        nonlocal current_thread_id

        if not current_thread_id:
            return

        send_chat_decision(
            current_thread_id,
            False
        )

        add_message(
            "AI DevOps Agent:\n\n"
            "❌ Workflow rejected.\n"
            "No branch or Merge Request was created."
        )

        current_thread_id = None

        page.update()

    input_box.on_submit = send_message

    return ft.Column(
        [
            ft.Text(
                "AI DevOps Agent",
                size=28,
                weight=ft.FontWeight.BOLD
            ),

            ft.Divider(),

            messages,

            ft.Row(
                [
                    input_box,

                    ft.ElevatedButton(
                        "Send",
                        on_click=send_message
                    )
                ]
            )
        ],
        expand=True
    )