import requests
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

TOKEN = os.getenv("GITLAB_TOKEN")
PROJECT_ID = os.getenv("GITLAB_PROJECT_ID")

# Authentication header
headers = {
    "PRIVATE-TOKEN": TOKEN
}

# GitLab Commits API endpoint
url = f"https://gitlab.com/api/v4/projects/{PROJECT_ID}/repository/commits"

# Send GET request
response = requests.get(url, headers=headers)

print("Status Code:", response.status_code)

if response.status_code == 200:
    commits = response.json()

    print(f"\nFound {len(commits)} commits\n")

    for commit in commits:
        print("=" * 50)
        print("Commit ID:", commit["short_id"])
        print("Author:", commit["author_name"])
        print("Message:", commit["title"])
        print("Created At:", commit["created_at"])
else:
    print(response.text)