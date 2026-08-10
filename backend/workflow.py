from workflow.graph import graph
from langgraph.types import Command

thread_id = "test-workflow-1"

config = {
    "configurable": {
        "thread_id": thread_id
    }
}


# Start the workflow
result = graph.invoke(
    {
        "user_request": "Create a login system using JWT."
    },
    config=config
)

print("\n===== WORKFLOW PAUSED =====")

interrupts = result.get("__interrupt__", [])

if interrupts:

    request = interrupts[0].value

    print("AI Analysis:", request["analysis"])
    print("Branch:", request["branch_name"])
    print("Commit:", request["commit_message"])
    print("MR Title:", request["mr_title"])

    choice = input("\nApprove? (y/n): ")

    approved = choice.lower() == "y"

    # Resume the same workflow
    result = graph.invoke(
        Command(resume=approved),
        config=config
    )

print("\n===== FINAL RESULT =====")
print(result)

