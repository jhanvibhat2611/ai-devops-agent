import requests
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

TOKEN = os.getenv("GITLAB_TOKEN")
PROJECT_ID = os.getenv("GITLAB_PROJECT_ID")

headers = {
    "PRIVATE-TOKEN": TOKEN
}

# GitLab Pipelines API endpoint
url = f"https://gitlab.com/api/v4/projects/{PROJECT_ID}/pipelines"

response = requests.get(url, headers=headers)

print("Status Code:", response.status_code)

if response.status_code == 200:
    pipelines = response.json()

    print(f"\nFound {len(pipelines)} pipelines\n")

    for pipeline in pipelines:
        print("=" * 50)
        print("Pipeline ID:", pipeline["id"])
        print("Status:", pipeline["status"])
        print("Ref:", pipeline["ref"])
        print("Created At:", pipeline["created_at"])
else:
    print(response.text)