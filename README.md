# 🤖 AI DevOps Agent

> **Built during my AI Internship at Enfec Technologies.**

An AI-powered DevOps agent that transforms natural language software requirements into tested code and GitLab Merge Requests through a human-in-the-loop workflow.

Built using **FastAPI, LangGraph, Qwen, Elasticsearch, GitLab API, JWT Authentication, and Flet**.

---

## 🚀 What it does

The user gives the agent a requirement such as:

> Create a Python function that checks whether a number is prime.

The agent then:

1. 🔍 Searches Elasticsearch for relevant Merge Request context
2. 🧠 Analyzes the requirement using an LLM
3. 🌿 Generates a branch name, commit message, and Merge Request title
4. 💻 Generates the implementation
5. 🧪 Generates and executes unit tests using `pytest`
6. 👤 Pauses for human approval
7. 🚀 Creates a Git branch and commits the generated code
8. 📤 Pushes the changes to GitLab
9. 🔀 Creates a Merge Request

The project also supports **AI-powered Merge Request reviews and code suggestions**.

---

## 🔄 Agent Workflow

```text
                         ┌──────────────────────┐
                         │   User Requirement   │
                         └──────────┬───────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────┐
                    │ Search Similar Merge Requests │
                    │       (Elasticsearch)         │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │    Analyze Requirement       │
                    │        using Qwen            │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │        Generate Code         │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │     Generate Unit Tests      │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │       Execute pytest         │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                         ┌──────────────────┐
                         │ Human Approval?  │
                         └────────┬─────────┘
                                  │
                     ┌────────────┴────────────┐
                     │                         │
                     ▼                         ▼
                ❌ Reject                  ✅ Approve
                     │                         │
                     ▼                         ▼
                    End                 Create Branch
                                              │
                                              ▼
                                         Commit Code
                                              │
                                              ▼
                                         Push to GitLab
                                              │
                                              ▼
                                      Create Merge Request
```

---

## ✨ Key Features

### 🧠 AI Requirement Analysis
Converts natural language requirements into structured development tasks, including:

- Requirement analysis
- Branch name generation
- Commit message generation
- Merge Request title generation

### 🔎 Context Retrieval with Elasticsearch
Stores and searches Merge Request metadata to retrieve relevant context before generating a solution.

### 💻 AI Code Generation
Generates implementation code based on the user's requirement and retrieved context.

### 🧪 Automated Unit Testing
Generates unit tests and executes them using `pytest` before proceeding with the workflow.

### 👤 Human-in-the-Loop Workflow
Uses **LangGraph interrupts and resume functionality** to pause the workflow and require explicit user approval before repository changes are made.

### 🌿 Git & GitLab Automation
After approval, the agent can automatically:

- Create a branch
- Write generated code
- Commit changes
- Push to GitLab
- Create a Merge Request

### 🔐 JWT Authentication
Implements JWT-based authentication and protects sensitive workflow actions.

### 🔍 AI Merge Request Review
Analyzes Merge Request diffs and generates AI-powered code review feedback.

### 💡 AI Code Suggestions
Generates improvement suggestions for Merge Request code and supports accepting AI-generated suggestions.

---

## 🏗️ Architecture

```text
┌──────────────┐
│    Flet UI   │
└──────┬───────┘
       │ HTTP + JWT
       ▼
┌──────────────────────┐
│   FastAPI Backend    │
└──────────┬───────────┘
           │
    ┌──────┼───────────────┐
    │      │               │
    ▼      ▼               ▼
┌────────┐ ┌─────────────┐ ┌──────────────┐
│LangGraph│ │Elasticsearch│ │  GitLab API  │
│Workflow │ │   Context   │ │ Repository   │
└────┬────┘ └─────────────┘ └──────────────┘
     │
     ▼
┌──────────────┐
│   Qwen LLM   │
│              │
│ • Analysis   │
│ • Code       │
│ • Tests      │
│ • Review     │
└──────────────┘
```

---

## 🛠️ Tech Stack

| Category | Technologies |
|---|---|
| Backend | Python, FastAPI |
| AI / Agent Workflow | Qwen, LangGraph |
| Search & Context | Elasticsearch |
| Authentication | JWT |
| Testing | Pytest |
| Git Integration | Git, GitLab API |
| Frontend | Flet |

---

## 📂 Project Structure

```text
ai-devops-agent/
│
├── backend/
│   ├── main.py
│   ├── workflow/
│   │   ├── graph.py
│   │   └── nodes.py
│   ├── storage/
│   │   ├── auth.py
│   │   └── database.py
│   ├── elasticsearch_client.py
│   └── ai_review.py
│
├── frontend/
│   ├── main.py
│   ├── api.py
│   └── views/
│
└── README.md
```

---

## ⚙️ Running Locally

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/ai-devops-agent.git
cd ai-devops-agent
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
```

**Windows**

```bash
venv\Scripts\activate
```

**Linux/macOS**

```bash
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file and configure the required credentials:

```env
JWT_SECRET_KEY=replace_with_a_long_random_secret
OLLAMA_AI_MODEL=qwen2.5-coder:7b
# Optional independent test model; defaults to OLLAMA_AI_MODEL:
# OLLAMA_TEST_MODEL=qwen2.5-coder:7b
GENERATED_CODE_FILE=generated_feature.py
# Optional frontend URL; default is http://127.0.0.1:8003
# AGENT_API_URL=http://127.0.0.1:8003
```

Use the name of an installed Ollama model. Elasticsearch and Ollama run locally on
ports 9200 and 11434. Register through the frontend to validate and encrypt your
personal GitLab token. Interactive operations never use a global project/token.
Start the frontend once to initialize the local database/key on a fresh install;
keep existing `frontend/users.db` and `frontend/secret.key` together. If the key is
missing for an existing account database, restore it rather than generating a replacement.

> **Never commit `.env` files, API keys, JWT secrets, or GitLab tokens to GitHub.**

### 5. Start the backend

```bash
cd backend
uvicorn main:app --port 8003 --workers 1
```

### 6. Start the frontend

```bash
cd frontend
python main.py
```

---

## 🎯 Project Motivation

This project explores how AI agents can automate repetitive parts of the software development lifecycle while keeping developers in control.

The core workflow follows a **human-in-the-loop approach**:

```text
AI analyzes → AI generates → AI tests → Human approves → Automation executes
```

---

## 🚧 Future Improvements

- OAuth-based GitLab integration
- Container/VM isolation for generated Python (current checks are prototype hardening)
- Persistent LangGraph checkpoints and restart recovery
- Full repository-aware, multi-file patching and code retrieval
- Dockerization
- CI/CD pipeline
- Background job processing

---

## 👩‍💻 Author

**Jhanvi Bhat**



## Repository-aware workflow and security

Login opens AI Agent chat. Send the development request first; when no repository
is bound, the conversation shows an authorized repository dropdown and resumes
that exact request after selection. The active repository stays visible. Change
repository starts a fresh conversation and is disabled while an approval or
execution is active. Navigating away and back preserves the Agent controls.

All interactive repository routes require a JWT and an explicit `project_id`.
The backend validates project access using that account's decrypted GitLab token
and derives clone URL/default branch from GitLab, never from client claims.
Approval additionally checks username, project, and immutable workflow ID.
Completed decisions are idempotent within the running process. Failed partial
writes are blocked from automatic resume; inspect GitLab before starting again.

New passwords use salted scrypt (N=131072, r=8, p=1). Successful legacy plaintext
logins atomically upgrade only that account. Password hashing, Fernet token
encryption, and JWT signing use separate mechanisms. `JWT_SECRET_KEY` is required
at backend startup; tokens and secrets are not printed.

Reviews are generated once and stored with user/project/MR/head SHA. Posting uses
that exact text, rejects a changed head, and verifies GitLab's response. Suggestions
are accepted by stored proposal ID, verify the MR source branch and full file
content, and include GitLab's atomic `last_commit_id` file precondition. See the
[GitLab commits API](https://docs.gitlab.com/api/commits/). Fork MR suggestion writes
are intentionally rejected until separate source-project authorization is added.
All changed MR files, including additions/deletions/renames, have base/head code
and Git diffs; an empty diff is handled explicitly.

Elasticsearch stores **MR metadata only**, keyed by `project_id:mr_iid`. Search
always filters by the selected project; old documents without project identity
are excluded. Listing MRs synchronizes all paginated results. ES outages yield
empty context. This is not repository-code RAG.

## Generated tests and workspace limits

The test agent treats the original request as the specification, analysis as
clarification, and generated code as the implementation being tested. It uses a
separate temperature-zero model, 1–5 fixed-input tests, import/AST checks, and at
most two structural repairs. A structurally valid assertion failure is preserved;
it is never repaired merely to make the implementation pass.

Before pytest, a conservative static allowlist rejects file/network/process
imports and unsafe builtins. Execution has a 10-second hard timeout, streamed
output capped at 16 KB, plugin autoload disabled, a minimal child environment, and
a temporary working directory cleaned on every path. These measures are **not a
production security sandbox**: generated Python still runs under the host user.
Only run this prototype on trusted requests. A container/VM with filesystem,
network, process, CPU and memory boundaries remains future work. The restricted
runner intentionally cannot validate arbitrary I/O-heavy applications.

The workflow writes one configured Python file, shown with the proposed code
before approval. Path traversal, absolute paths, Git metadata paths and symlink
escapes are rejected. Unrelated repository files are preserved. Workspaces remain
under `backend/workspaces/<project_id>/<workflow_uuid>`; credentials are supplied
through temporary askpass helpers, never remote URLs. Existing origins must match.
There is no force push. Workspaces are retained for inspection; remove only completed
job directories after verifying no work is needed. Automatic retention cleanup,
general multi-file patches and crash recovery are deferred.

## Database migration and local data

Approval history adds nullable `project_id` and `thread_id` columns in place and
an idempotency index. Existing rows are retained with unknown project identity;
they are excluded from project-scoped history rather than guessed into a project.
Migration runs during frontend initialization and on history access. Legacy
password migration runs only after successful login. The database is not replaced.
Webhook delivery IDs are persisted in the same SQLite database.

Local `.env`, keys, databases, JSON account data, workspaces and caches are ignored.
Previously tracked key/database files were removed from the index only. Their old
contents can still exist in Git history: rotate exposed GitLab tokens, encryption
keys (with token re-encryption), and signing secrets as applicable. Coordinate any
history cleanup separately; this change does not rewrite history or delete local data.

## Webhooks (optional)

Configure `GITLAB_WEBHOOK_SECRET`, `GITLAB_WEBHOOK_TOKEN` (a dedicated service token),
and comma-separated `GITLAB_WEBHOOK_PROJECT_IDS`. Configure the identical secret
in GitLab's webhook settings. `/webhook/gitlab` checks `X-Gitlab-Token`, uses the
payload's allowlisted project ID, and deduplicates `X-Gitlab-Event-UUID` (or a payload
hash) in SQLite. AI suggestion commits are ignored to prevent loops. Push and MR
events can generate and post suggestion notes for that project only.

Completed, in-progress, and failed delivery IDs are not replayed automatically.
A failed or interrupted delivery may have partial external effects; inspect it
before deliberate recovery. Distributed delivery guarantees are deferred.

## Checks and deployment scope

Run `python -m pytest` and `python -m compileall -q backend frontend tests` from
the repository root. Tests cover real scrypt/SQLite migrations, JWTs, real pytest
subprocesses (including known wrong implementations and timeout), real LangGraph
interrupt/rejection, Flet callbacks, and mocked GitLab isolation/write failures.
`RUN_LIVE_TESTS=1` opts into the read-only local Elasticsearch health test.

Run a single backend worker. Conversations, pending requests, review/suggestion
proposals, and MemorySaver checkpoints are process-local and expire on restart.
Do not claim durable jobs or production readiness. Background workers, distributed
locks, durable checkpoints, HTTPS deployment, advanced observability, a hardened
execution sandbox and full CI/CD infrastructure remain future work.


## Completion record (2026-10-02)

| Gap | Result |
| --- | --- |
| Inline repository selection and pending request continuation | Fixed |
| JWT and selected-project authorization across interactive routes | Fixed |
| Workflow ownership and repeated-decision side effects | Fixed within one running worker |
| Secret logging, required JWT secret, password hashing/migration, Git tracking | Fixed; historical exposure remains |
| Specification-first test contract, bounded repair and subprocess hardening | Fixed for prototype scope; no production sandbox |
| Suggestion models, server proposals, stale revisions and verified writes | Fixed; fork-source writes deferred |
| Exact stored reviews and stale review rejection | Fixed; revision check and note creation are not a GitLab transaction |
| Supervisor MR metadata, pagination, base/head diffs and all-file UI | Fixed |
| Elasticsearch project identity and graceful retrieval failure | Fixed for MR metadata |
| Approval-history project identity | Fixed with non-destructive nullable-column migration |
| Authenticated and deduplicated webhooks | Practical version implemented; distributed/crash recovery deferred |
| Explicit generated-file target and safe per-workflow Git workspaces | Fixed for single-file workflow; automatic cleanup deferred |

Validation: 62 tests passed with local Elasticsearch enabled; compileall and
`git diff --check` passed. Warnings are existing Flet ElevatedButton and Starlette
httpx deprecations. Tests used pinned project dependencies in a temporary C: Python
environment because the original venv references a missing interpreter and D: had
insufficient space for a new environment. The incomplete validation .venv was removed;
the original venv was preserved. No alternative project or implementation copy was made.

Live checks: Elasticsearch HTTP 200; Ollama model-list HTTP 200 (four models).
The explicitly authorized check of one saved GitLab account returned HTTP 401;
repository discovery and GitLab write flows could not be validated live. No live
branch, commit, MR, comment or webhook write was performed. Ollama generation and
native desktop visual appearance were not manually exercised; graph, subprocess
and Flet callback behavior were tested locally.

Changed/added source, configuration and documentation files:

- `.gitignore`
- `README.md`
- `backend/elasticsearch_client.py`
- `backend/gitlab/client.py`
- `backend/main.py`
- `backend/storage/account_routes.py`
- `backend/storage/approval_history.py`
- `backend/storage/auth.py`
- `backend/storage/database.py`
- `backend/storage/passwords.py`
- `backend/workflow/nodes.py`
- `backend/workflow/safety.py`
- `backend/workflow/state.py`
- `backend/workflow/test_agent.py`
- `backend/workflow/workspace.py`
- `frontend/api.py`
- `frontend/chat.py`
- `frontend/login.py`
- `frontend/storage.py`
- `frontend/views/agent.py`
- `frontend/views/branches.py`
- `frontend/views/merge_requests.py`
- `frontend/views/review.py`
- `frontend/views/search.py`
- `frontend/views/suggestions.py`
- `pytest.ini`
- `requirements.txt`
- `tests/conftest.py`
- `tests/test_es.py`
- `tests/test_integration_contracts.py`
- `tests/test_security_api.py`
- `tests/test_test_contract.py`

Index-only removals (all local copies preserved):

- `backend/secret.key`
- `backend/users.db`
- `frontend/secret.key`
- `frontend/users.db`
- `users.json`
