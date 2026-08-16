import flet as ft

from api import (
    start_chat,
    send_chat_decision,
    post_ai_review,
    post_ai_suggestion,
    accept_ai_suggestion
)


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

    # ============================================================
    # FRONTEND STATE
    # ============================================================

    current_thread_id = None
    current_intent = None

    # ============================================================
    # RESET AGENT STATE
    # ============================================================

    def reset_agent_state():

        nonlocal current_thread_id
        nonlocal current_intent

        current_thread_id = None
        current_intent = None

        messages.controls.clear()
        input_box.value = ""

        page.update()

    # ============================================================
    # ADD MESSAGE
    # ============================================================

    def add_message(
        text,
        is_user=False
    ):

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

    # ============================================================
    # SEND MESSAGE
    # ============================================================

    def send_message(e):

        nonlocal current_thread_id
        nonlocal current_intent

        message = input_box.value.strip()

        if not message:
            return

        # --------------------------------------------------------
        # Show user message
        # --------------------------------------------------------

        add_message(
            f"You: {message}",
            is_user=True
        )

        input_box.value = ""

        page.update()

        # --------------------------------------------------------
        # Send request to backend
        # --------------------------------------------------------

        response = start_chat(
            message,
            current_thread_id
        )

        # --------------------------------------------------------
        # Save intent
        # --------------------------------------------------------

        if response.get("intent"):

            current_intent = response["intent"]

        # --------------------------------------------------------
        # Save thread ID
        # --------------------------------------------------------

        if response.get("thread_id"):

            current_thread_id = response["thread_id"]

        # ========================================================
        # MERGE REQUEST SELECTION
        # ========================================================

        if response.get("type") == "mr_selection":

            message_text = response.get(
                "message",
                "Please select a Merge Request."
            )

            add_message(
                f"AI DevOps Agent:\n\n"
                f"{message_text}"
            )

            merge_requests = response.get(
                "merge_requests",
                []
            )

            if not merge_requests:

                add_message(
                    "No Merge Requests were found."
                )

                page.update()
                return

            add_message(
                "Available Merge Requests:"
            )

            # ----------------------------------------------------
            # Create MR selection buttons
            # ----------------------------------------------------

            for mr in merge_requests:

                mr_id = mr.get("mr_iid")

                title = mr.get(
                    "title",
                    "Untitled Merge Request"
                )

                branch = mr.get(
                    "source_branch",
                    ""
                )

                if branch:

                    button_text = (
                        f"MR !{mr_id} — {title}\n"
                        f"Branch: {branch}"
                    )

                else:

                    button_text = (
                        f"MR !{mr_id} — {title}"
                    )

                # ------------------------------------------------
                # Capture MR ID safely
                # ------------------------------------------------

                def select_mr(
                    e,
                    selected_mr_id=mr_id
                ):

                    nonlocal current_thread_id
                    nonlocal current_intent

                    if current_intent == "review":

                        selected_message = (
                            f"review MR "
                            f"{selected_mr_id}"
                        )

                    elif current_intent == "suggestion":

                        selected_message = (
                            f"suggest MR "
                            f"{selected_mr_id}"
                        )

                    else:

                        selected_message = (
                            f"suggest MR "
                            f"{selected_mr_id}"
                        )

                    add_message(
                        f"You: {selected_message}",
                        is_user=True
                    )

                    page.update()

                    selected_response = start_chat(
                        selected_message,
                        current_thread_id
                    )

                    if selected_response.get(
                        "thread_id"
                    ):

                        current_thread_id = (
                            selected_response[
                                "thread_id"
                            ]
                        )

                    if selected_response.get(
                        "intent"
                    ):

                        current_intent = (
                            selected_response[
                                "intent"
                            ]
                        )

                    handle_response(
                        selected_response
                    )

                messages.controls.append(
                    ft.Container(
                        content=ft.ElevatedButton(
                            button_text,
                            on_click=select_mr
                        ),
                        padding=5
                    )
                )

            page.update()
            return

        # ========================================================
        # HANDLE RESPONSE
        # ========================================================

        handle_response(response)

    # ============================================================
    # HANDLE BACKEND RESPONSE
    # ============================================================

    def handle_response(response):

        nonlocal current_thread_id
        nonlocal current_intent

        # --------------------------------------------------------
        # Thread ID
        # --------------------------------------------------------

        if response.get("thread_id"):

            current_thread_id = (
                response["thread_id"]
            )

        # --------------------------------------------------------
        # Intent
        # --------------------------------------------------------

        if response.get("intent"):

            current_intent = (
                response["intent"]
            )

        # ========================================================
        # AI CODE REVIEW
        # ========================================================

        if response.get("type") == "review":

            mr_id = response.get(
                "mr_iid"
            )

            review = response.get(
                "review",
                "Unable to generate review."
            )

            add_message(
                f"AI Code Review:\n\n"
                f"{review}"
            )

            def post_review(e):

                result = post_ai_review(
                    mr_id
                )

                if result.get(
                    "status"
                ) == "posted":

                    add_message(
                        "✅ AI review successfully "
                        "posted to GitLab."
                    )

                else:

                    add_message(
                        "❌ Failed to post AI review "
                        "to GitLab.\n\n"
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

            mr_id = response.get(
                "mr_iid"
            )

            suggestions = response.get(
                "suggestions",
                []
            )

            if not suggestions:

                add_message(
                    "AI Code Suggestions:\n\n"
                    "No code improvements suggested."
                )

            else:

                for i, suggestion in enumerate(
                    suggestions,
                    start=1
                ):

                    file_path = suggestion.get(
                        "file",
                        "Unknown"
                    )

                    function_name = suggestion.get(
                        "function_name",
                        "Unknown"
                    )

                    current_code = suggestion.get(
                        "current_code",
                        ""
                    )

                    suggested_code = suggestion.get(
                        "suggested_code",
                        ""
                    )

                    reason = suggestion.get(
                        "reason",
                        ""
                    )

                    suggestion_text = (
                        f"AI Code Suggestion {i}\n\n"
                        f"File: {file_path}\n\n"
                        f"Function: {function_name}\n\n"
                        f"Current Code:\n"
                        f"{current_code}\n\n"
                        f"Suggested Code:\n"
                        f"{suggested_code}\n\n"
                        f"Reason:\n"
                        f"{reason}"
                    )

                    add_message(
                        suggestion_text
                    )

                    # ------------------------------------------------
                    # Accept suggestion
                    # ------------------------------------------------

                    def accept_suggestion(
                        e,
                        mr_id=mr_id,
                        file_path=file_path,
                        current_code=current_code,
                        suggested_code=suggested_code
                    ):

                        result = accept_ai_suggestion(
                            mr_id,
                            file_path,
                            current_code,
                            suggested_code
                        )

                        if result.get(
                            "status"
                        ) == "accepted":

                            add_message(
                                "✅ Suggestion accepted.\n\n"
                                "The suggested code was "
                                "applied and committed to "
                                "the Merge Request source "
                                "branch.\n\n"
                                f"Commit: "
                                f"{result.get('commit_url', '')}"
                            )

                        else:

                            add_message(
                                "❌ Failed to apply "
                                "suggestion.\n\n"
                                f"{result.get('message', result)}"
                            )

                        page.update()

                    # ------------------------------------------------
                    # Reject suggestion
                    # ------------------------------------------------

                    def reject_suggestion(e):

                        add_message(
                            "❌ Suggestion rejected.\n\n"
                            "No changes were made to GitLab."
                        )

                        page.update()

                    messages.controls.append(
                        ft.Row(
                            [
                                ft.ElevatedButton(
                                    "Accept Suggestion",
                                    on_click=accept_suggestion
                                ),

                                ft.OutlinedButton(
                                    "Reject Suggestion",
                                    on_click=reject_suggestion
                                )
                            ]
                        )
                    )

            page.update()
            return

        # ========================================================
        # LANGGRAPH HUMAN APPROVAL
        # ========================================================

        if response.get(
            "status"
        ) == "waiting_for_approval":

            current_thread_id = (
                response["thread_id"]
            )

            proposal = (
                "AI DevOps Agent:\n\n"
                f"Analysis:\n"
                f"{response['analysis']}\n\n"
                f"Branch: "
                f"{response['branch_name']}\n\n"
                f"Commit: "
                f"{response['commit_message']}\n\n"
                f"MR Title: "
                f"{response['mr_title']}\n\n"
                f"Generated Code:\n"
                f"{response.get(
                    'generated_code',
                    'No generated code available.'
                )}"
            )

            add_message(
                proposal
            )

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

            page.update()
            return

        # ========================================================
        # LANGGRAPH COMPLETED / NORMAL RESPONSE
        # ========================================================

        result = response.get(
            "result",
            {}
        )

        if not isinstance(result, dict):

            add_message(
                "AI DevOps Agent:\n\n"
                "The backend returned an unexpected response."
            )

            page.update()
            return

        # ========================================================
        # VALIDATION FAILED
        # ========================================================

        if result.get(
            "request_valid"
        ) is False:

            validation_message = result.get(
                "validation_message",
                "Please provide a valid development task."
            )

            add_message(
                "AI DevOps Agent:\n\n"
                f"❌ {validation_message}"
            )

            page.update()
            return

        # ========================================================
        # SECURITY FAILURE
        # ========================================================

        security_passed = result.get(
            "security_passed"
        )

        if security_passed is False:

            security_report = result.get(
                "security_report",
                ""
            )

            security_summary = ""

            if isinstance(
                security_report,
                dict
            ):

                security_summary = (
                    security_report.get(
                        "summary",
                        ""
                    )
                )

                findings = security_report.get(
                    "findings",
                    []
                )

                if findings:

                    findings_text = "\n".join(
                        f"• {finding}"
                        for finding in findings
                    )

                else:

                    findings_text = (
                        "No detailed findings provided."
                    )

            else:

                findings_text = str(
                    security_report
                )

            security_message = (
                "AI DevOps Agent:\n\n"
                "🔐 Security Review\n\n"
                "❌ Security check failed.\n\n"
            )

            if security_summary:

                security_message += (
                    f"Summary:\n"
                    f"{security_summary}\n\n"
                )

            security_message += (
                f"Security Findings:\n"
                f"{findings_text}\n\n"
                "🚫 Workflow stopped.\n"
                "No branch, commit, or Merge Request "
                "was created."
            )

            add_message(
                security_message
            )

            page.update()
            return

        # ========================================================
        # UNIT TEST FAILURE
        # ========================================================

        test_passed = result.get(
            "test_passed"
        )

        if test_passed is False:

            test_result = result.get(
                "test_result",
                "No test result available."
            )

            add_message(
                "AI DevOps Agent:\n\n"
                "🧪 Unit Tests\n\n"
                "❌ Generated tests failed.\n\n"
                f"{test_result}\n\n"
                "🚫 Workflow stopped.\n"
                "The code was not committed."
            )

            page.update()
            return

        # ========================================================
        # COMPLETED WORKFLOW
        # ========================================================

        message_text = response.get(
            "message"
        )

        if message_text:

            add_message(
                "AI DevOps Agent:\n\n"
                f"{message_text}"
            )

            page.update()
            return

        # --------------------------------------------------------
        # Build a clean workflow summary
        # --------------------------------------------------------

        summary_parts = [
            "AI DevOps Agent:"
        ]

        analysis = result.get(
            "analysis"
        )

        if analysis:

            summary_parts.extend(
                [
                    "",
                    "🧠 Analysis:",
                    str(analysis)
                ]
            )

        generated_code = result.get(
            "generated_code"
        )

        if generated_code:

            summary_parts.extend(
                [
                    "",
                    "💻 Generated Code:",
                    generated_code
                ]
            )

        test_passed = result.get(
            "test_passed"
        )

        if test_passed is True:

            summary_parts.extend(
                [
                    "",
                    "🧪 Unit Tests:",
                    "✅ All generated tests passed."
                ]
            )

        security_passed = result.get(
            "security_passed"
        )

        if security_passed is True:

            summary_parts.extend(
                [
                    "",
                    "🔐 Security Review:",
                    "✅ Security checks passed."
                ]
            )

        branch_name = result.get(
            "branch_name"
        )

        commit_message = result.get(
            "commit_message"
        )

        mr_title = result.get(
            "mr_title"
        )

        if branch_name:

            summary_parts.extend(
                [
                    "",
                    f"Branch: {branch_name}"
                ]
            )

        if commit_message:

            summary_parts.extend(
                [
                    f"Commit: {commit_message}"
                ]
            )

        if mr_title:

            summary_parts.extend(
                [
                    f"MR Title: {mr_title}"
                ]
            )

        mr_url = result.get(
            "mr_url"
        )

        if mr_url:

            summary_parts.extend(
                [
                    "",
                    f"Merge Request: {mr_url}"
                ]
            )

        if len(summary_parts) == 1:

            summary_parts.extend(
                [
                    "",
                    "No additional workflow information available."
                ]
            )

        add_message(
            "\n".join(summary_parts)
        )

        page.update()

    # ============================================================
    # APPROVE WORKFLOW
    # ============================================================

    def approve(e):

        nonlocal current_thread_id
        nonlocal current_intent

        if not current_thread_id:
            return

        response = send_chat_decision(
            current_thread_id,
            True
        )

        mr_url = response.get(
            "mr_url"
        )

        if mr_url:

            message = (
                "AI DevOps Agent:\n\n"
                "✅ Workflow approved.\n\n"
                f"Merge Request created:\n"
                f"{mr_url}"
            )

        else:

            message = (
                "AI DevOps Agent:\n\n"
                "⚠️ Workflow was approved, "
                "but the Merge Request "
                "could not be created."
            )

        add_message(
            message
        )

        current_thread_id = None
        current_intent = None

        page.update()

    # ============================================================
    # REJECT WORKFLOW
    # ============================================================

    def reject(e):

        nonlocal current_thread_id
        nonlocal current_intent

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
        current_intent = None

        page.update()

    # ============================================================
    # ENTER KEY
    # ============================================================

    input_box.on_submit = send_message

    # ============================================================
    # UI
    # ============================================================

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
                    ),

                    ft.OutlinedButton(
                        "New Chat",
                        on_click=lambda e:
                        reset_agent_state()
                    )
                ]
            )
        ],
        expand=True
    )