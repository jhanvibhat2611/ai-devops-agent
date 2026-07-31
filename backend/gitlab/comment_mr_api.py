import requests
from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv("GITLAB_TOKEN")
PROJECT_ID = os.getenv("GITLAB_PROJECT_ID")

headers = {
    "PRIVATE-TOKEN": TOKEN
}

MR_IID = 1

url = f"https://gitlab.com/api/v4/projects/{PROJECT_ID}/merge_requests/{MR_IID}/notes"

payload = {
    "body": "Reviewed using GitLab API and Python requests."
}

response = requests.post(
    url,
    headers=headers,
    data=payload
)

print("Status Code:", response.status_code)

if response.status_code == 201:

    note = response.json()

    print("\n===== COMMENT ADDED =====")
    print("Comment:", note["body"])

else:
    print(response.text)