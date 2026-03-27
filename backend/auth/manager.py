import json
import os
import bcrypt

CREDS_FILE = "/root/web-vps-manager/data/credentials.json"


def is_setup_done() -> bool:
    return os.path.exists(CREDS_FILE)


def create_user(username: str, password: str):
    os.makedirs(os.path.dirname(CREDS_FILE), exist_ok=True)
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    with open(CREDS_FILE, "w") as f:
        json.dump({"username": username, "password": hashed}, f)


def verify_user(username: str, password: str) -> bool:
    if not is_setup_done():
        return False
    with open(CREDS_FILE, "r") as f:
        data = json.load(f)
    if data["username"] != username:
        return False
    return bcrypt.checkpw(password.encode(), data["password"].encode())
