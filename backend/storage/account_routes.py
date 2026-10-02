"""Account routes; GitLab token validation precedes encrypted storage."""
import sqlite3
import os
import requests
import jwt
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .auth import verify_user, create_user, user_exists
app = APIRouter()
JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24
class LoginRequest(BaseModel):
    username: str
    password: str
class RegisterRequest(LoginRequest):
    gitlab_token: str

@app.post("/login")
async def login_user(user: LoginRequest):

    if not verify_user(
        user.username,
        user.password
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    expiration = datetime.now(
        timezone.utc
    ) + timedelta(
        hours=JWT_EXPIRE_HOURS
    )

    payload = {
        "sub": user.username,
        "exp": expiration
    }

    token = jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM
    )


    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user.username
    }

# ============================================================
# REGISTER USER
# ============================================================

@app.post("/register")
async def register_user(
    request: RegisterRequest
):

    username = (
        request.username
        or ""
    ).strip()

    password = (
        request.password
        or ""
    )

    gitlab_token = (
        request.gitlab_token
        or ""
    ).strip()

    # ========================================================
    # BASIC VALIDATION
    # ========================================================

    if not all(
        [
            username,
            password,
            gitlab_token
        ]
    ):

        raise HTTPException(
            status_code=400,
            detail="All fields are required."
        )

    # ========================================================
    # CHECK APPLICATION USERNAME
    # ========================================================

    if user_exists(
        username
    ):

        raise HTTPException(
            status_code=409,
            detail=(
                "Username already exists. "
                "Please choose another username."
            )
        )

    # ========================================================
    # VALIDATE GITLAB TOKEN
    # ========================================================

    try:

        gitlab_response = requests.get(
            "https://gitlab.com/api/v4/user",
            headers={
                "PRIVATE-TOKEN": gitlab_token
            },
            timeout=20
        )

    except requests.RequestException as error:


        raise HTTPException(
            status_code=502,
            detail=(
                "Unable to connect to GitLab. "
                "Please try again."
            )
        )

    # --------------------------------------------------------
    # Invalid / expired token
    # --------------------------------------------------------

    if gitlab_response.status_code == 401:

        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid or expired GitLab "
                "access token."
            )
        )

    # --------------------------------------------------------
    # Other GitLab errors
    # --------------------------------------------------------

    if gitlab_response.status_code != 200:

        raise HTTPException(
            status_code=400,
            detail=(
                "GitLab authentication failed. "
                f"GitLab returned status "
                f"{gitlab_response.status_code}."
            )
        )

    # ========================================================
    # GET AUTHENTICATED GITLAB IDENTITY
    # ========================================================

    gitlab_user = (
        gitlab_response.json()
    )

    actual_gitlab_username = (
        gitlab_user.get(
            "username",
            ""
        )
        or ""
    ).strip()

    if not actual_gitlab_username:

        raise HTTPException(
            status_code=400,
            detail=(
                "GitLab token was valid, but "
                "the authenticated GitLab username "
                "could not be determined."
            )
        )

    # ========================================================
    # CREATE USER
    # ========================================================

    try:

        create_user(
            username=username,
            password=password,
            gitlab_username=(
                actual_gitlab_username
            ),
            gitlab_token=gitlab_token
        )

    except sqlite3.IntegrityError:

        raise HTTPException(
            status_code=409,
            detail=(
                "Username already exists."
            )
        )

    except Exception as error:


        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to create account."
            )
        )

    # ========================================================
    # SUCCESS
    # ========================================================

    return {
        "status": "registered",
        "username": username,
        "gitlab_username": (
            actual_gitlab_username
        ),
        "message": (
            "Registration successful. "
            "Please log in."
        )
    }
