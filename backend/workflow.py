from workflow.graph import graph



result = graph.invoke(
    {
        "user_request": "Create a login system using JWT."
    }
)

print(result)

