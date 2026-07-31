import requests
from dotenv import load_dotenv
import os
import urllib.parse

# Load variables from .env
load_dotenv()

TOKEN = os.getenv("GITLAB_TOKEN")
PROJECT_ID = os.getenv("GITLAB_PROJECT_ID")

# GitLab authentication header
headers = {
    "PRIVATE-TOKEN": TOKEN
}

# File we want to read from the repository
file_path = "README.md"

# Encode file path for URL safety
encoded_path = urllib.parse.quote(file_path, safe='')

# Repository Files API endpoint
url = (
    f"https://gitlab.com/api/v4/projects/"
    f"{PROJECT_ID}/repository/files/"
    f"{encoded_path}"
)

# Branch from which file should be read
params = {
    "ref": "main"
}

# Send GET request to GitLab
response = requests.get(
    url,
    headers=headers,
    params=params
)

print("Status Code:", response.status_code)

if response.status_code == 200:
    data = response.json()

    print("\n===== FILE DETAILS =====")
    print("File Name:", data["file_name"])
    print("File Path:", data["file_path"])
    print("Branch:", data["ref"])
    print("Last Commit ID:", data["last_commit_id"])

else:
    print(response.text)


