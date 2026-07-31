import requests
from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv("GITLAB_TOKEN")
PROJECT_ID = os.getenv("GITLAB_PROJECT_ID")

headers = {
    "PRIVATE-TOKEN": TOKEN
}

url = f"https://gitlab.com/api/v4/projects/{PROJECT_ID}"

response = requests.get(url, headers=headers)

print("Status Code:", response.status_code)

if response.status_code == 200:
    data = response.json()
    print("Project Name:", data["name"])
else:
    print(response.text)