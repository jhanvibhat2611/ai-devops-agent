import requests
from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv("GITLAB_TOKEN")
PROJECT_ID = os.getenv("GITLAB_PROJECT_ID")

headers = {
    "PRIVATE-TOKEN": TOKEN
}

MR_IID = 1  # replace with your MR IID

url = f"https://gitlab.com/api/v4/projects/{PROJECT_ID}/merge_requests/{MR_IID}"

response = requests.get(url, headers=headers)

print("Status Code:", response.status_code)

if response.status_code == 200:

    mr = response.json()

    print("\n===== MR DETAILS =====")
    print("Title:", mr["title"])
    print("State:", mr["state"])
    print("Source Branch:", mr["source_branch"])
    print("Target Branch:", mr["target_branch"])
    print("Description:", mr["description"])

else:
    print(response.text)