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

# Branches API endpoint
# GET /projects/:id/repository/branches
url = f"https://gitlab.com/api/v4/projects/{PROJECT_ID}/repository/branches"

# Send GET request
response = requests.get(url, headers=headers)

print("Status Code:", response.status_code)

if response.status_code == 200:

    branches = response.json()

    print(f"\nFound {len(branches)} branches\n")

    for branch in branches:

        print("=" * 50)
        print("Branch Name:", branch["name"])
        print("Protected:", branch["protected"])
        print("Default Branch:", branch["default"])

else:
    print(response.text)