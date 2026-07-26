import requests
from dotenv import load_dotenv
import os

# Load .env variables
load_dotenv()

TOKEN = os.getenv("GITLAB_TOKEN")
PROJECT_ID = os.getenv("GITLAB_PROJECT_ID")

headers = {
    "PRIVATE-TOKEN": TOKEN
}

# List Merge Requests API
url = f"https://gitlab.com/api/v4/projects/{PROJECT_ID}/merge_requests"

response = requests.get(url, headers=headers)

print("Status Code:", response.status_code)

if response.status_code == 200:

    merge_requests = response.json()

    for mr in merge_requests:

        print("=" * 50)
        print("MR IID:", mr["iid"])
        print("Title:", mr["title"])
        print("State:", mr["state"])
        print("Author:", mr["author"]["name"])

else:
    print(response.text)