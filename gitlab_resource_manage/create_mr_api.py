import requests
from dotenv import load_dotenv
import os

# Load variables from .env
load_dotenv()

TOKEN = os.getenv("GITLAB_TOKEN")
PROJECT_ID = os.getenv("GITLAB_PROJECT_ID")

# GitLab authentication
headers = {
    "PRIVATE-TOKEN": TOKEN
}

# Create Merge Request API endpoint
url = f"https://gitlab.com/api/v4/projects/{PROJECT_ID}/merge_requests"

# Data for the MR
payload = {
    "source_branch": "feature/test-api",   # your new branch
    "target_branch": "main",
    "title": "Test Merge Request from API"
}

# Send POST request
response = requests.post(
    url,
    headers=headers,
    data=payload
)

print("Status Code:", response.status_code)

if response.status_code == 201:

    mr = response.json()

    print("\n===== MERGE REQUEST CREATED =====")
    print("MR IID:", mr["iid"])
    print("Title:", mr["title"])
    print("State:", mr["state"])
    print("Source Branch:", mr["source_branch"])
    print("Target Branch:", mr["target_branch"])

else:
    print(response.text)

