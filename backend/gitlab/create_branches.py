import requests
from dotenv import load_dotenv
import os

# Load variables from .env
load_dotenv()

TOKEN = os.getenv("GITLAB_TOKEN")
PROJECT_ID = os.getenv("GITLAB_PROJECT_ID")

# GitLab authentication header
headers = {
    "PRIVATE-TOKEN": TOKEN
}

# Create Branch API endpoint
# POST /projects/:id/repository/branches
url = f"https://gitlab.com/api/v4/projects/{PROJECT_ID}/repository/branches"

# Data to send
payload = {
    "branch": "feature/test-api",
    "ref": "main"
}

# Send POST request
response = requests.post(
    url,
    headers=headers,
    params=payload
)

print("Status Code:", response.status_code)

if response.status_code == 201:

    branch = response.json()

    print("\n===== BRANCH CREATED =====")
    print("Branch Name:", branch["name"])
    print("Protected:", branch["protected"])
    print("Default:", branch["default"])

else:
    print(response.text)


