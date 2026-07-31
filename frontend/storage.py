import json
import os

USERS_FILE = "users.json"


def load_users():
    if not os.path.exists(USERS_FILE):
        return {}

    with open(USERS_FILE, "r") as file:
        return json.load(file)


def save_users(users):
    with open(USERS_FILE, "w") as file:
        json.dump(users, file, indent=4)


def user_exists(username):
    users = load_users()
    return username in users


def verify_user(username, password):
    users = load_users()

    if username not in users:
        return False

    return users[username]["password"] == password