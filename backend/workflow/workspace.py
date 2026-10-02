"""Per-workflow Git workspace with credential-free remotes and scoped writes."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
from workflow.safety import target_path
from storage.auth import get_gitlab_token


def commit_generated_code(state):
    project_id = int(state["gitlab_project_id"])
    if project_id <= 0:
        raise ValueError("Invalid project identity.")
    import uuid
    job = str(uuid.UUID(state["thread_id"]))
    root = Path(__file__).resolve().parents[1] / "workspaces" / str(project_id)
    workspace = root / job
    clone_url = state["gitlab_clone_url"]
    parsed = urlsplit(clone_url)
    if parsed.scheme != "https" or parsed.hostname != "gitlab.com" or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Expected the authorized GitLab HTTPS clone URL without credentials.")
    file_path = target_path(state["target_file"])
    branch = state["branch_name"]
    if not branch or branch.startswith("-"):
        raise ValueError("Invalid branch name.")
    token = get_gitlab_token(state["username"])
    if not token:
        raise ValueError("GitLab credentials unavailable.")
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="agent_askpass_") as directory:
        helper = Path(directory, "askpass.py")
        helper.write_text("import os,sys\nprint('oauth2' if 'username' in sys.argv[1].lower() else os.environ['GITLAB_GIT_TOKEN'])\n", encoding="utf-8")
        wrapper = Path(directory, "askpass.cmd" if os.name == "nt" else "askpass.sh")
        if os.name == "nt":
            wrapper.write_text(f'@echo off\r\n"{sys.executable}" "{helper}" %*\r\n', encoding="utf-8")
        else:
            import shlex
            wrapper.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(helper))} "$@"\n')
            wrapper.chmod(0o700)
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(GIT_ASKPASS=str(wrapper), GIT_TERMINAL_PROMPT="0", GITLAB_GIT_TOKEN=token)
        def git(args, cwd=None, check=True):
            result = subprocess.run(["git", "-c", "credential.helper=", "-c", "core.hooksPath=" + directory, *args],
                cwd=cwd, env=env, capture_output=True, text=True, timeout=120)
            if check and result.returncode:
                # Never return raw command stderr: Git/credential helpers may include secrets.
                raise RuntimeError(f"Git {args[0]} failed (exit {result.returncode}). Workspace retained for inspection.")
            return result
        git(["check-ref-format", "--branch", branch])
        if workspace.exists():
            if not (workspace / ".git").is_dir():
                raise RuntimeError("Incomplete workflow workspace; manual inspection required.")
            if git(["remote", "get-url", "origin"], workspace).stdout.strip().rstrip("/") != clone_url.rstrip("/"):
                raise RuntimeError("Workspace origin does not match authorized repository.")
            if git(["status", "--porcelain"], workspace).stdout.strip():
                raise RuntimeError("Workflow workspace has uncommitted changes; refusing to overwrite.")
        else:
            git(["clone", "--no-checkout", "--", clone_url, str(workspace)])
        git(["fetch", "origin", branch], workspace)
        git(["checkout", "-B", branch, "FETCH_HEAD"], workspace)
        destination = workspace / file_path
        if not destination.resolve().is_relative_to(workspace.resolve()):
            raise ValueError("Generated target escapes workspace through a symlink.")
        if any(p.is_symlink() for p in [destination, *destination.parents] if p != workspace.parent):
            raise ValueError("Symlink targets are not supported.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(state["generated_code"].rstrip() + "\n", encoding="utf-8")
        git(["add", "--", file_path], workspace)
        changed = git(["diff", "--cached", "--quiet"], workspace, check=False)
        if changed.returncode == 1:
            git(["-c", "user.name=AI DevOps Agent", "-c", "user.email=ai-devops-agent@localhost", "commit", "-m", state["commit_message"]], workspace)
        elif changed.returncode != 0:
            raise RuntimeError("Unable to inspect staged changes.")
        git(["push", "origin", branch], workspace)
    return {"generated_code": state["generated_code"]}
