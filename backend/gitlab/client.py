"""Explicit project/token transport. No ambient GitLab credentials."""
from urllib.parse import quote
import requests
from fastapi import HTTPException

BASE = "https://gitlab.com/api/v4"


def request(method, endpoint, project_id, token, **kwargs):
    if not project_id or not token:
        raise HTTPException(400, "An authorized project and user token are required.")
    return api_request(method, f"projects/{int(project_id)}/{endpoint}".rstrip("/"), token, **kwargs)


def api_request(method, endpoint, token, **kwargs):
    try:
        response = requests.request(method, f"{BASE}/{endpoint}", headers={"PRIVATE-TOKEN": token},
                                    timeout=30, **kwargs)
    except requests.RequestException:
        raise HTTPException(502, "Unable to reach GitLab.") from None
    if not 200 <= response.status_code < 300:
        status = response.status_code if response.status_code in (400, 401, 403, 404, 409, 422, 429) else 502
        raise HTTPException(status, f"GitLab rejected the operation (HTTP {response.status_code}).")
    try:
        return response.json(), response.headers
    except ValueError:
        raise HTTPException(502, "GitLab returned invalid JSON.") from None


def get(endpoint, project_id, token):
    return request("GET", endpoint, project_id, token)[0]


def post(endpoint, payload, project_id, token):
    return request("POST", endpoint, project_id, token, json=payload)[0]


def pages(endpoint, project_id, token, params=None):
    result, page = [], 1
    while True:
        data, headers = request("GET", endpoint, project_id, token,
                                params={**(params or {}), "per_page": 100, "page": page})
        if not isinstance(data, list):
            raise HTTPException(502, "Invalid GitLab collection response.")
        result.extend(data)
        following = headers.get("X-Next-Page")
        if not following:
            return result
        page = int(following)


def file_data(path, ref, project_id, token):
    return get(f"repository/files/{quote(path, safe='')}?ref={quote(ref, safe='')}", project_id, token)
